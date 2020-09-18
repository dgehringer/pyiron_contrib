import numpy as np
import matplotlib.pylab as plt
import ipywidgets as widgets
from IPython.display import display
from pyiron.atomistics.structure.periodic_table import PeriodicTable


class GUI_PSE:
    def __init__(self, width=30, height=25, button_sep_width=5):
        self.pse = PeriodicTable()
        self.description = None
        self._width = '{}px'.format(int(width))
        self._height = '{}px'.format(int(height))
        self._width_sep = '{}px'.format(int(width + button_sep_width))

        df = self.pse.dataframe.sort_values('AtomicNumber')
        self.el = df.Abbreviation
        self.group = df.Group
        self.period = df.Period

        self.pse_grid = [[widgets.HBox([], layout=widgets.Layout(width=self._width, height=self._height)) for _ in range(np.max(self.group))] for _ in range(np.max(self.period))]
        for e, g, p in zip(self.el, self.group, self.period):
            w = widgets.Button(description=e, layout=widgets.Layout(width=self._width, height=self._height))
            w.on_click(self.refresh)
            self.pse_grid[p-1][g-1] = w
            
    def on_click(self, func):
        self._func = func
            
    def refresh(self, b):
        self.description = b.description 
        self._func(b)
        
    def gui(self):
        flatten = lambda l: [item for sublist in l for item in sublist] 
        return widgets.GridBox(flatten(self.pse_grid), 
                layout=widgets.Layout(
                    height='230px', 
                    grid_template_columns="repeat({}, {})".format(np.max(self.group), self._width_sep)))


class GUI_PLOT:
    def __init__(self, job):
        self.job = job

        plt.ioff()
        self._ax=plt.gca()
        self.out_plt = widgets.Output()

        self.tab = widgets.Tab()
        titles = ['Animate', 'Energy', 'Temperature', 'Positions']
        
        [self.tab.set_title(i, t) for i, t in enumerate(titles)]
        self.tab.children = len(self.tab._titles) * [self.plot_selected(None)]
        self.tab.observe(self.plot_selected, type='change')   

    def plot_selected(self, b): 
        sel_index = self.tab.selected_index
        title = self.tab.get_title(sel_index)
        return eval ('self.plot_{}()'.format(title)) 

    def plot_Animate(self):
        view = self.job.animate_structure()
        view_gui = GUI_3D(view)

        self.out_plt.clear_output(wait=True)
        with self.out_plt:
            display(view_gui.gui())  
        return self.out_plt 

    def plot_Temperature(self):
        ax, job = self._init_plot()
        ax.set_title('Temperature vs time')
        ax.set_xlabel('Time [fs]')
        ax.set_ylabel('Temperature [K]')
        x = job['output/generic/time'][1:]
        ax.plot(x, job['output/generic/temperature'][1:])
        return self.plot()           

    def plot_Energy(self):
        ax, job = self._init_plot()
        ax.set_title('Energy vs time')
        ax.set_xlabel('Time [fs]')
        ax.set_ylabel('Energy [eV]')
        x = job['output/generic/time'][1:]
        ax.plot(x, job['output/generic/energy_pot'][1:], label='E_pot')
        ax.plot(x, job['output/generic/energy_tot'][1:], label='E_tot')
        ax.legend()
        return self.plot() 

    def plot_Positions(self):
        ax, job = self._init_plot()
        ax.set_title('Positions vs time')
        ax.set_xlabel('Time [fs]')
        ax.set_ylabel('z [$\AA$]')
        x = job['output/generic/time']
        y = job['output/generic/unwrapped_positions'][:,:,2]
        ax.plot(x, y)
        return self.plot()  

    def _init_plot(self):
        self._ax.clear()
        return self._ax, self.job                  

    def plot(self):
        self.out_plt.clear_output(wait=True)
        with self.out_plt:
            display(self._ax.figure)  
        return self.out_plt             

    def gui(self):
        return self.tab    


class GUI_3D:
    def __init__(self, view, delay=100, width=400, height=400):
        self.view = view
        self.max_frame = view.max_frame
        self.delay = delay
        self.width = '{}px'.format(int(width))
        self.height = '{}px'.format(int(height))
        # print('max_frame: ', self.max_frame)
        
        self.play = widgets.Play(
            value=0,
            min=0,
            max=self.max_frame,
            step=1,
            interval=self.delay,
            description="Press play",
            disabled=False
        )
        self.play.observe(self.refresh_play, names='value')
        self.slider = widgets.IntSlider()
        widgets.jslink((self.play, 'value'), (self.slider, 'value'))
        self.view_option = widgets.Dropdown(
            options=['spacefill', 'ball+stick'],
            description=''
        )
        self.view_radius = widgets.Dropdown(
            options=['0.1', '0.2', '0.5', '1', '1.5', '2'],
            value = '1',
            description=''
        )
        self.view_index = widgets.Text(description='Index:')


        self.refresh_view_opt()

        self.view_option.observe(self.refresh_view_opt, names='value')
        self.view_radius.observe(self.refresh_view_opt, names='value')
        self.view.observe(self.view_clicked, names='picked')

    def view_clicked(self,b):
        print (b['new']['atom1']['index']) 
        self.view_index.value = str(b['new']['atom1']['index'])

    def refresh_view_opt(self, *args):
        self.view.clear_representations()
        self.view.add_representation(self.view_option.value, 
            radius=float(self.view_radius.value)
            )   
           
    def refresh_play(self, b):
        self.view.frame = b['new']        
    
    def gui(self):
        self.view.background = 'black'
        self.view._remote_call('setSize', target='Widget', args=[self.width, self.height])
        self.view.camera = 'orthographic'
        if self.max_frame == 0:
            return widgets.VBox([self.view, widgets.HBox([self.view_option, self.view_radius], layout=widgets.Layout(width='400px')), self.view_index])
        return widgets.VBox([self.view, widgets.HBox([self.play, self.slider])]) 
    
    # def _repr_html_(self):
    #     return display(self.gui())

class GUI_Data:
    def __init__(self,project,msg=None):
        self.project = project
        self.msg = msg

class GUI_Structure:
    def __init__(self, project, msg=None):
        self.project = project
        self.msg = msg
        self._pse_gui = GUI_PSE(width=30)
        
        self.count = 0
        self.create_btn = widgets.Button(description='Refresh') 
        # self.output_plot3d = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))
        self.output_plot3d = widgets.Output()
        self.cubic_ckb = widgets.Checkbox(value=True, description='Cubic')
        self.ortho_ckb = widgets.Checkbox(value=False, description='Orthorombic')

        self.el1_btn = widgets.Button(description='Al', layout=widgets.Layout(width='50px', height='25px'))
        self.el1_btn.on_click(self.set_el1_btn)   
        # self.set_el1_btn(self.el1_btn)   # select this button to start with PSE input 
        self.set_el1_btn(None)   # select this button to start with PSE input        

        self.repeat_drp = widgets.Dropdown(
            options=range(1, 6),
            value=1,
            description='Repeat:'
        )

        self.cubic_ckb.observe(self.refresh, names='value')
        self.ortho_ckb.observe(self.refresh, names='value')
        self.repeat_drp.observe(self.refresh, names='value')
        self.create_btn.on_click(self.refresh)
        self.refresh()

    def set_el1_btn(self, b):
        self._pse_gui.on_click(self.refresh_el1)

    def refresh_el1(self, b):
        self.el1_btn.description = b.description
        self.refresh()    
        
    def gui(self):
        return widgets.HBox([
            widgets.VBox([self.el1_btn, self.repeat_drp, self.cubic_ckb, self.ortho_ckb]),  # , self.create_btn]), 
            self.output_plot3d, self._pse_gui.gui()])  
        
    def refresh(self, *args):
        self.msg.clear_output()
        with self.msg:
            print ('ase: ', self.el1_btn.description, self.cubic_ckb.value, self.ortho_ckb.value, self.repeat_drp.value)
        try:
            struc = self.project.create_ase_bulk(self.el1_btn.description, cubic=self.cubic_ckb.value, orthorhombic=self.ortho_ckb.value).repeat(self.repeat_drp.value)
        except (RuntimeError, ValueError) as e:
            self.output_plot3d.clear_output()
            # self.msg.clear_output()
            with self.output_plot3d:
                print ('Error: ', e)
                return
        self.structure = struc

        self.view = struc.plot3d()
        self.view_gui = GUI_3D(self.view)

        self.output_plot3d.clear_output() #wait=True)
        with self.output_plot3d:
            # print long string to prevent bug in nglview in connection with HBox
            print ('Display                                      ')
            display(self.view_gui.gui())


class PARAM_MD:
    def __init__(self, GUI_CALC):
        self.gui_calc = GUI_CALC
        
        self.temperature = widgets.IntSlider(description='Temperature: ', min=1, max=5000, step=10, value=500)
        self.n_ionic_steps = widgets.Dropdown(
            options= [int(10**i) for i in range(8)],
            value=10000,
            description='n_ionic_steps:'
        )
        self.n_print = widgets.Dropdown(
            options= [int(10**i) for i in range(6)],
            value=100,
            description='n_print:'
        ) 
        
    def gui(self):
        self.temperature.observe(self.gui_calc.refresh, names='value')
        self.n_ionic_steps.observe(self.gui_calc.refresh, names='value')
        self.n_print.observe(self.gui_calc.refresh, names='value')
        
        return widgets.VBox([self.temperature, self.n_ionic_steps, self.n_print], layout={'border': '1px solid lightgray'})


class PARAM_MIN:
    def __init__(self, gui_calc):
        self.gui_calc = gui_calc
    
        self.f_eps = widgets.Dropdown(
            options= [10**(-i) for i in range(5)],
            value=10**(-4),
            description='Force conv.:'
        )

        self.max_iter = widgets.Dropdown(
            options= [int(10**(i)) for i in range(5)],
            value=100,
            description='max iterations:'
        )
        self.n_print = widgets.Dropdown(
            options= [int(10**i) for i in range(6)],
            value=100,
            description='n_print:'
        ) 
        
    def gui(self):
        self.f_eps.observe(self.gui_calc.refresh, names='value')
        self.max_iter.observe(self.gui_calc.refresh, names='value')
        self.n_print.observe(self.gui_calc.refresh, names='value')
        
        return widgets.VBox([self.f_eps, self.max_iter, self.n_print], layout={'border': '1px solid lightgray'})
        

def get_generic_inp(job):
    j_dic = job['input/generic/data_dict']
    return {k:v for k,v in zip(j_dic['Parameter'], j_dic['Value'])}

class PARAM_IMG:
    def __init__(self, GUI_CALC):
        self.gui_calc = GUI_CALC

        self.f_eps = widgets.Dropdown(
            options=[10 ** (-i) for i in range(5)],
            value=10 ** (-4),
            description='Force conv.:'
        )

    def gui(self):
        return widgets.VBox([self.f_eps], layout={'border': '1px solid lightgray'})

class GUI_CALC_EXPERIMENTAL:
    def __init__(self, msg=None):
        self.msg = msg
        self.par_img=PARAM_IMG(self)

        calc_opt = widgets.Tab()
        calc_opt.set_title(0, 'ImageJob')
        calc_opt.set_title(1, 'Minimize')

        calc_opt.children = [self.par_img.gui(), widgets.VBox()]
        # calc_opt.selected_index = 0
        self.calc_opt = calc_opt

        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))
        self.job_type="ImageJob"
        self.job_name = widgets.Text(
            value='',
            placeholder='Type something',
            description='Job Name:',
            disabled=False
        )
        self.job_name.continuous_update = False

        self.create_btn = widgets.Button(description='Refresh')
        self.run_btn = widgets.Button(description='Run')
        self.run_btn.style.button_color = 'lightblue'

        self.filter_type = widgets.Dropdown(
            options=['brightness_filter', 'gaussian', 'sobel'],
            value='brightness_filter',
            description='Filter Type:'
        )


        self.mask = self.multi_checkbox_widget(["img1","img2"])
            #= [w.description for w in widgets.children[1].children if w.value]

    def multi_checkbox_widget(self,descriptions):
        options_dict = {description: widgets.Checkbox(description=description, value=False) for description in descriptions}
        options = [options_dict[description] for description in descriptions]
        multi_select = widgets.VBox(options, layout={'overflow': 'scroll'})
        return multi_select

    def set_job(self, job, i_step=-1):
        self.job = job
        self.project = job.project

        self.job_name.value = job.job_name
#       self.potential.options = self.job.list_potentials()
#       self.potential.value = self.job.potential['Name'][0]

        self.run_btn.style.button_color = 'red'
        self.run_btn.description = 'Delete'
        self.output.clear_output()

    def set_gui_structure(self, gui_structure):
        self.gui_structure = gui_structure
        self.project = gui_structure.project
#       self.struc = gui_structure.structure
        self.job_name.value = ""
        self.refresh_job_name()

        self.job = self.project.create_job(self.job_type, self.job_name.value)

    def refresh(self, job=None, *args):
        pass

    def refresh_job_name(self, *args):
        # self.output.clear_output()
        if self.job_name.value in self.project.list_nodes():
            job = self.project.load(self.job_name.value)
            self.set_job(job)
        else:
            self.run_btn.style.button_color = 'lightgreen'
            self.run_btn.description = 'Run'
            self.output.clear_output()

    def on_run_btn_clicked(self, b):
        if b.description == 'Run':
            self.msg.clear_output()
            with self.msg:
                print('running')
            self.job = self.project.create_job(self.job_type.value, self.job_name.value)
#           if self.calc_opt.selected_index == 0:
#               self.job.calc_md(temperature=self.par_md.temperature.value,
#                                n_ionic_steps=self.par_md.n_ionic_steps.value, n_print=self.par_md.n_print.value)
#           else:
#               self.job.calc_static()
            self.job.add_images('datasets/Setarah_Mg5Al3Ca_2percentDef/SE_10*.tif', as_gray=True,
               metadata={
                   'owner': 'Setareh Medghalchi',
                   'composition': 'Mg5Al3Ca',
                   'deformation': '2%'
               })
            self.job.images[1].filters.gaussian(sigma=3)
            self.job.run()
            self.refresh_job_name()

            self.msg.clear_output()
            with self.msg:
                print('finished')
        elif b.description == 'Delete':
            self.job.remove()
            self.job._status = None  # TODO: should be done by remove!
            self.refresh_job_name()

    def gui(self):
        # self.job_type.observe(self.refresh, names='value')
        self.job_name.observe(self.refresh_job_name, names='value')
        # self.potential.observe(self.refresh, names='value')

        self.create_btn.on_click(self.refresh)
        self.run_btn.on_click(self.on_run_btn_clicked)
        job_box = widgets.VBox([self.filter_type, self.job_name,self.mask], layout={'border': '1px solid lightgray'})

        return widgets.HBox([widgets.VBox([self.calc_opt, job_box, self.create_btn, self.run_btn]), self.output])

class GUI_CALC_ATOMISTIC:
    def __init__(self, msg=None):
        self.par_md = PARAM_MD(self)
        self.par_min = PARAM_MIN(self)
        self.msg = msg
        
        calc_opt = widgets.Tab()
        calc_opt.set_title(0, 'MD')
        calc_opt.set_title(1, 'Minimize')
        calc_opt.set_title(2, 'Static')

        calc_opt.children = [self.par_md.gui(), self.par_min.gui(), widgets.VBox()] 
        # calc_opt.selected_index = 0
        self.calc_opt = calc_opt
        
        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))

        self.job_name = widgets.Text(
            value='',
            placeholder='Type something',
            description='Job Name:',
            disabled=False
        )
        self.job_name.continuous_update = False

        self.create_btn = widgets.Button(description='Refresh')
        self.run_btn = widgets.Button(description='Run')
        self.run_btn.style.button_color ='lightblue'

        self.job_type = widgets.Dropdown(
            options = ['Lammps', 'Vasp', 'ImageJob'],
            value='ImageJob',
            description='Job Type:'
        )

        self.potential = widgets.Dropdown(
            options = [''], 
            description='Potential:'
        )

    def set_job(self, job, i_step=-1):
        self.job = job
        self.project = job.project
        self.struc = job.get_structure(i_step)

        self.job_name.value = job.job_name
        self.potential.options = self.job.list_potentials() 
        self.potential.value = self.job.potential['Name'][0]
        self.set_job_params(job)

        self.run_btn.style.button_color ='red'
        self.run_btn.description = 'Delete'
        view = self.job.animate_structure()
        self.view_gui = GUI_3D(view)
        self.output.clear_output()
        with self.output:
            display(self.view_gui.gui())  
        self.refresh_input()       

    def set_gui_structure(self, gui_structure):
        self.gui_structure = gui_structure
        self.project = gui_structure.project
        self.struc = gui_structure.structure
        self.view_gui = gui_structure.view_gui
        self.job_name.value = ""
        self.refresh_input() 
        self.refresh_job_name()
  
        
    def set_job_params(self, job):
        self.struc = job.get_structure(-1)  # TODO: i_frame
        self.potential.options = job.list_potentials()  
        self.potential.value = job.potential['Name'].values[0]
        generic_par = get_generic_inp(job)
        with self.output:
            print ('calc mode: ', generic_par['calc_mode'])
        if generic_par['calc_mode'] == 'md':
            self.calc_opt.selected_index = 0
            self.par_md.temperature.value = int(generic_par['temperature'])
            self.par_md.n_ionic_steps.value = int(generic_par['n_ionic_steps']) 
        elif generic_par['calc_mode'] == 'minimize':
            self.calc_opt.selected_index = 1
            # self.par_min.value = 
        elif generic_par['calc_mode'] == 'static':
            self.calc_opt.selected_index = 2
                
    def refresh_input(self, *args):
        if self.struc is None:
            with self.output:
                print ('No structure')
            return widgets.HBox([self.output])    

        if self.job_name.value == "":
            self.job_name.value = self.struc.get_chemical_formula()    

        self.job = self.project.create_job(self.job_type.value, self.job_name.value)
        if self.job.status == 'finished':
            self.set_job_params(self.job)
        else:    
            self.job.structure = self.struc
            self.potential.options = self.job.list_potentials()     
        
    def refresh(self, job=None, *args):
        pass
        
    def refresh_job_name(self, *args):     
        # self.output.clear_output()    
        if self.job_name.value in self.project.list_nodes():
            job = self.project.load(self.job_name.value)
            self.set_job(job)
        else:
            if self.job.status == 'finished':
                self.struc = self.job.get_structure(self.view_gui.view.frame)
                view = self.struc.plot3d()
                self.view_gui = GUI_3D(view)
            self.run_btn.style.button_color ='lightgreen'
            self.run_btn.description = 'Run'
            self.output.clear_output()
            with self.output:
                print ('frame: ', self.view_gui.view.frame, self.calc_opt.selected_index)
                display(self.view_gui.gui())  
                # print ("test: ", self.job_name.value, pr.list_nodes(), self.job_name.value in pr.list_nodes(), self.run_btn.style.button_color) 
            
    def on_run_btn_clicked(self, b):
        if b.description == 'Run':
            self.msg.clear_output()
            with self.msg:
                print ('running')
            self.job = self.project.create_job(self.job_type.value, self.job_name.value)
            self.job.structure = self.struc
            self.job.potential = self.potential.value
            if self.calc_opt.selected_index == 0:
                self.job.calc_md(temperature=self.par_md.temperature.value, n_ionic_steps=self.par_md.n_ionic_steps.value, n_print=self.par_md.n_print.value)
            elif self.calc_opt.selected_index == 1: 
                self.job.calc_minimize(f_tol=self.par_min.f_eps.value, max_iter=self.par_min.max_iter.value, n_print=self.par_min.n_print.value)
            else:
                self.job.calc_static()
            self.job.run()
            self.refresh_job_name()

            self.msg.clear_output()
            with self.msg:
                print ('finished')
        elif b.description == 'Delete':
            self.job.remove()
            self.job._status = None  # TODO: should be done by remove!
            self.refresh_job_name()
            self.refresh_input()
                 
    def gui(self):
        # self.job_type.observe(self.refresh, names='value')
        self.job_name.observe(self.refresh_job_name, names='value')
        # self.potential.observe(self.refresh, names='value')

        self.create_btn.on_click(self.refresh)   
        self.run_btn.on_click(self.on_run_btn_clicked)
        job_box = widgets.VBox([self.job_type, self.job_name, self.potential], layout={'border': '1px solid lightgray'})

        return widgets.HBox([widgets.VBox([self.calc_opt, job_box, self.create_btn, self.run_btn]), self.output])      


class GUI_EXPLORER:
    def __init__(self, project, msg=None):
        self.project = project
        self.msg = msg
        self.job = None
        
        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))        
        self.groups = widgets.Select(options=[], description='Group:')
        self.nodes = widgets.Select(options=[], description='Nodes:')
        self._update()

        self.groups.observe(self.refresh_group, names='value')
        self.nodes.observe(self.refresh_node, names='value')
        
    def refresh(self, *args):
        pass
    
    @property
    def structure(self):
        if self.view is not None:
            return self.node.get_structure(self.view.frame)
        
    def gui(self):
        return widgets.HBox([
            widgets.VBox([self.groups, self.nodes]), 
            self.output])  
    
    def _update(self):
        groups = [".", ".."] + self.project.list_groups()
        nodes = ["."] + self.project.list_nodes()
        self.groups.options = groups
        self.nodes.options = nodes        
        
    def refresh_group(self, *args):
        if self.groups.value != '.':
            self.project = self.project[self.groups.value]
            self._update() 

    def refresh_node(self, *args):
        self.view = None
        if self.nodes.value is not None:
            node = self.project[self.nodes.value] 
            self.job = node
            if hasattr(node, 'animate_structure'):
                self.output.clear_output()
                with self.output:
                    print ('animate')
                    # self.view = node.animate_structure()
                    self.gui_plot = GUI_PLOT(node)
                    # view = self.job.animate_structure()
                    # self.view_gui = GUI_3D(view)
                    # display(self.view_gui.gui())
                    display(self.gui_plot.gui())
                    self.node = node
            elif hasattr(node, 'list_groups'):
                self.project = node 
                self._update()                     


class GUI_PYIRON:    
    def __init__(self, project):
        self.msg = widgets.Output(layout={'border': '1px solid black'})
        self.msg.append_stdout('')
        self.msg.append_stderr('')
        self.clear_msg = widgets.Button(description='Clear')
        self.project=project
        

    def on_clear_msg_clicked(self, b):
        self.msg.clear_output()

    def on_proceed_clicked(self):
        if self.pyiron_type.value=="Atomistic":
            self.tabtitle=['Structure','Calculate','Explorer']
            self.gui_input = GUI_Structure(project=self.project, msg=self.msg)
            self.gui_calc = GUI_CALC_ATOMISTIC(msg=self.msg)
        elif self.pyiron_type.value=="Experimental":
            self.tabtitle=['Data','Calculate','Explorer']
            self.gui_input = GUI_Data(project=self.project, msg=self.msg)
            self.gui_calc = GUI_CALC_EXPERIMENTAL(msg=self.msg)
        else:
            print("Err: This should be impossible")
            exit()
        self.gui_explorer = GUI_EXPLORER(project)
        self.gui_work()

    def gui(self):
        self.pyiron_type = widgets.Dropdown(
            options = ['Atomistic', 'Experimental'],
            description='Choose PyIron branch:'
        )
        run_btn = widgets.Button(description='Proceed')
        run_btn.on_click(self.on_proceed_clicked())
        return widgets.VBox([self.pyiron_type ,run_btn, widgets.HBox([self.msg, self.clear_msg])], layout={'border': '4px solid lightgray'})

    def gui_work(self):

        tab = widgets.Tab()
        for tabidx in len(self.tabtitle):
            tab.set_title(tabidx, self.tabtitle[tabidx])
        #tab.children = [self.gui_explorer.gui()]
        #tab.children = [self.gui_calc_experiment.gui(), self.gui_explorer.gui()]
        tab.children = [self.gui_input.gui(), self.gui_calc.gui(), self.gui_explorer.gui()]

        #self.tab_children = [self.gui_explorer]
        self.tab_children = [self.gui_input,self.gui_calc, self.gui_explorer]
        #self.tab_children = [self.gui_structure, self.gui_calc, self.gui_explorer]

        def on_value_change(change):
            sel_old = change['old']
            sel_ind = change['new']
            if sel_old == 0:
                self.gui_calc.set_gui_input(self.gui_input)
            elif sel_old == 1:
                self.gui_calc.set_job(self.gui_explorer.job)
            self.msg.clear_output()
            with self.msg:
                print ('sel: ', sel_old, sel_ind)
                # print (sel_ind, type(tab.children[sel_ind]), hasattr(self.tab_children[sel_ind], 'refresh'))
            self.tab_children[sel_ind].refresh()
            
            
        self.clear_msg.on_click(self.on_clear_msg_clicked)
        tab.observe(on_value_change, names='selected_index')
        return widgets.VBox([tab, widgets.HBox([self.msg, self.clear_msg])], layout={'border': '4px solid lightgray'})                                                 