import numpy as np
import matplotlib.pylab as plt
import ipywidgets as widgets
from ipywidgets import interact
from IPython.display import display
import IPython.display as IPyDisplay
from pyiron.atomistics.structure.periodic_table import PeriodicTable
import os
from glob import iglob
from pyiron_contrib.image.image import Image
from pyiron_contrib.image.S3ObjectDB import S3ObjectDB


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
        #print('start gui PSE')
        flatten = lambda l: [item for sublist in l for item in sublist]
        return widgets.GridBox(flatten(self.pse_grid),
                layout=widgets.Layout(
                    height='230px',
                    grid_template_columns="repeat({}, {})".format(np.max(self.group), self._width_sep)))


class GUI_PLOT:
    def __init__(self, job):
        self.job = job
        self.project=job.project

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
        #print('start gui Plot')
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
        #print (b['new']['atom1']['index'])
        self.view_index.value = str(b['new']['atom1']['index'])

    def refresh_view_opt(self, *args):
        self.view.clear_representations()
        self.view.add_representation(self.view_option.value,
            radius=float(self.view_radius.value)
            )

    def refresh_play(self, b):
        self.view.frame = b['new']

    def gui(self):
        #print('start gui', self)
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
        self.filewidget=FileBrowser(self.project)
        self.msg = msg
    def refresh(self):
        pass
    def _get_data(self):
        self.data=self.filewidget.list_data()
    def list_data(self):
        self._get_data()
        return self.data
    def gui(self):
        #print('start gui', self)
        self.filebrws = self.filewidget.widget()
#       self.data_name = widgets.Text(
#           value='',
#           placeholder='Type something',
#           description='File Name:',
#           disabled=False
#       )
        return self.filebrws

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
        #print('start gui', self)
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
            #print ('Display                                      ')
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
        #print('start gui', self)
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
        #print('start gui', self)
        self.f_eps.observe(self.gui_calc.refresh, names='value')
        self.max_iter.observe(self.gui_calc.refresh, names='value')
        self.n_print.observe(self.gui_calc.refresh, names='value')

        return widgets.VBox([self.f_eps, self.max_iter, self.n_print], layout={'border': '1px solid lightgray'})


def get_generic_inp(job):
    j_dic = job['input/generic/data_dict']
    return {k:v for k,v in zip(j_dic['Parameter'], j_dic['Value'])}


# taken from  https://stackoverflow.com/questions/39495994/uploading-files-using-browse-button-in-jupyter-and-using-saving-them
class FileBrowser(object):
    #ToDo:
    #       Make text-field searchable / autocomplete? .
    #       Use S3 store to search for data  -  for now: download data into tmp_dir which is rm after some time?
    #           Need to abstract the file search method to cover local file system and S3
    #           Need upload method - upon choose files > upload them, ask for meta-data  >> Convert to own class <<
    #                                                                                   Needed for File upload to S3
    def __init__(self,project):
        self.project=project
        self.path = os.getcwd()
        self.data=[]
        self.box2_value=self.path
        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))
        self._clickedFiles=[]
        self.s3path="data"
        self._data_access=S3ObjectDB(self.project,config_file="/home/nsiemer/pyiron/projects/config.json",group=self.s3path)
        self.path_storage=['','data']
        self.data_sys='local'
        self._update_files()


    def _update_files(self):
        if self.data_sys == "local":
            self.files = list()
            self.dirs = list()
            if(os.path.isdir(self.path)):
                for f in iglob(self.path+'/*'):
                    if os.path.isdir(f):
                        self.dirs.append(os.path.split(f)[1])
                    else:
#                       self.files.append(f)
                        self.files.append(os.path.split(f)[1])
        else:
            self._data_access.open(self.path)
            self.files = self._data_access.list_nodes()
            self.dirs = self._data_access.list_groups()

    def widget(self):
        self.pathbox = widgets.HBox(layout=widgets.Layout(width='100%', justify_content='flex-start'))
        self.box = widgets.VBox(layout=widgets.Layout(width='50%', height='100%',justify_content='flex-start'))
        self.box2=widgets.Text(description="(rel) Path")
        button=widgets.Button(description='Set Path', tooltip="Sets current path to provided string.")
        button2=widgets.Button(description="Choose File(s)",
                               tooltip='Loads currently activated files and all files '+
                                       'matching the provided string patten; wildcards allowed!')
        button3=widgets.Button(description="Reset election")
        file_sys_button=widgets.Button(description='S3',tooltip="Change to S3 Datastore")
        def on_sys_change(b):
            self._clickedFiles = []
            if b.description == 'S3':
                self.path_storage[0]=self.path
                self.path=self.path_storage[1]
                b.description='local'
                self.data_sys='S3'
                b.tooltip="Change to local Filesystem"
                self._update_files()
                self._update(self.box)
                self.box2_value=self.path
                return
            if b.description == 'local':
                self.path_storage[1]=self.path
                self.path=self.path_storage[0]
                b.description='S3'
                self.data_sys='local'
                b.tooltip="Change to S3 Datastore"
                self._update_files()
                self._update(self.box)
                self.box2_value=self.path
                return

        def on_click(b):
            #print("entered on_click: b=",b)
            self.output.clear_output(True)
            with self.output:
                print('')
            if b.description == 'Set Path':
                if self.data_sys =='S3':
                    path='/'+self.path
                else:
                    path=self.path
                if len(self.box2.value)==0:
                    with self.output:
                        print('No path given')
                    return
                elif self.box2.value[0] != '/':
                    with self.output:
                        print('current path=',path)
                    path=path+'/'+self.box2.value
                else:
                    path=self.box2.value
                # check path consistency:
                if (self.data_sys == 'local' and self.path.exists(path) ):
                    self.path=os.path.abspath(path)
                elif (self._data_access.is_dir(path[1:]) and self.data_sys == 'S3'):
                    self.path=path[1:]
                else:
                    self.box2.__init__(description="(rel) Path",value='')
                    with self.output:
                        print('No valid path')
                    return
                self.box2_value=self.path
                self._update_files()
                self._update(self.box)
                self.box2.__init__(description="(rel) Path",value='')
            if b.description == 'Choose File(s)':
                if self.data_sys=='S3':
                    return
                if len(self.box2.value) ==0:
                    path=self.path
                elif self.box2.value[0] != '/':
                    path=self.box2_value+'/'+self.box2.value
                else:
                    path=self.box2.value
                #print ('try to append:',self.box2_value)
                appendlist = []
                for f in iglob(path):
                    #print('append to self.data:',f)
                    if os.path.isfile(f):
                        self.data.append(f)
                        appendlist.append(f)
                for f in self._clickedFiles:
                    self.data.append(f)
                    appendlist.append(f)
                with self.output:
                    if len(appendlist) > 0:
                        print ('Loaded %i File(s):' %(len(appendlist)))
                        for i in appendlist:
                            print(i)
                    else:
                        print('No files chosen')
            if b.description == 'Reset election':
               self._clickedFiles=[]
               self._update(self.box)

        self._update(self.box)
        button.on_click(on_click)
        button2.on_click(on_click)
        button3.on_click(on_click)
        file_sys_button.on_click(on_sys_change)
        return widgets.VBox([widgets.HBox([file_sys_button,self.box2,button,button2,button3]),
                             self.pathbox,widgets.HBox([self.box,self.output])])

    def list_data(self):
        return self.data

    def _update_pathbox(self,box):
        def on_click(b):
            self.path = b.path
            self.box2_value = self.path
            self._update_files()
            self._update(self.box)
            self.box2.__init__(description="(rel) Path", value='')
        buttons=[]
        tmppath=self.path
        tmppath_old=self.path+'/'
        while tmppath != tmppath_old:
            tmppath_old=tmppath
            [tmppath,dir] = os.path.split(tmppath)
            button=widgets.Button(description=dir+'/',layout=widgets.Layout(width='auto'))
            button.style.button_color = '#DDDDAA'
            button.path=tmppath_old
            button.on_click(on_click)
            buttons.append(button)
        button=widgets.Button(icon="fa-home",layout=widgets.Layout(width='auto'))
        button.style.button_color='#999999'
        if self.data_sys == 'local':
            button.path=os.getcwd()
        else:
            button.path=self.s3path
        button.on_click(on_click)
        buttons.append(button)
        buttons.reverse()
        box.children = tuple(buttons)

    def _update(self, box):
        self.output.clear_output(True)
        def on_click(b):
            self.path = os.path.join(self.path, b.description)
            self.box2_value=self.path
            self._update_files()
            self._update(box)
        def on_click_file(b):
            f=os.path.join(self.path, b.description)
            if self.data_sys == 'local':
                self.output.clear_output(True)
                Display_file(f,self.output)
            if f in self._clickedFiles:
                b.style.button_color = '#DDDDDD'
                self._clickedFiles.remove(f)
            else:
                b.style.button_color = '#FFBBBB'
                self._clickedFiles.append(f)

        buttons = []
        #if self.files:
        #button = widgets.Button(description='..')
        #button.style.button_color = '#9999FF'
        #button.on_click(on_click)
        #buttons.append(button)
        for f in self.dirs:
            button = widgets.Button(description=f,icon="fa-folder",layout=widgets.Layout(width='min-content', justify_content='flex-start'))
            button.style.button_color = '#9999FF'
            button.on_click(on_click)
            buttons.append(button)
        for f in self.files:
            button = widgets.Button(description=f,icon="fa-file-o",layout=widgets.Layout(width='min-content', justify_content='flex-start'))
            if os.path.join(self.path,f) in self._clickedFiles:
                button.style.button_color = '#FFBBBB'
            else:
                button.style.button_color = '#DDDDDD'
            button.on_click(on_click_file)
            buttons.append(button)
        box.children = tuple(buttons)
        self._update_pathbox(self.pathbox)

class Display_file():
    #TODO:
    '''
/home/nsiemer/pyiron.git/pyiron_contrib/pyiron_contrib/image/image.py:259: RuntimeWarning: More than 20 figures have been opened. Figures created through the pyplot interface (`matplotlib.pyplot.figure`) are retained until explicitly closed and may consume too much memory. (To control this warning, see the rcParam `figure.max_open_warning`).
  fig, ax = plt.subplots(**subplots_kwargs)
    '''
    def __init__(self,path,outwidget):
        self.path=path
        self.output=outwidget
        _, filetype = os.path.splitext(path)
        if filetype.lower() in ['.tif','.tiff']:
            self.display_tiff()
        elif filetype.lower() in ['.jpg','.jpeg','.png','.gif']:
            self.display_img()
        elif filetype.lower() in ['.txt']:
            self.display_txt()
        else:
            self.diplay_default()
    def display_tiff(self):
        plt.ioff()
        img=Image(self.path)
        fig, ax =img.plot()
        with self.output:
            display(fig)
    def display_txt(self):
        with self.output:
            with open(self.path) as f:
                print(f.read(),end='')
    def display_img(self):
        with self.output:
            display(IPyDisplay.Image(self.path))
    def diplay_default(self):
        try:
            with self.output:
                display(self.path)
        except:
            with self.output:
                print(self.path)


class PARAM_IMG:
    #brightness filter
    def __init__(self, GUI_CALC):
        self.gui_calc = GUI_CALC
        self.option = widgets.Dropdown(description='None', value=None)
    def gui(self):
        return widgets.VBox()
class PARAM_IMG2:
    #gaussian
    def __init__(self, GUI_CALC):
        self.gui_calc = GUI_CALC
        self.option = widgets.FloatSlider(description='sigma: ', min=0, max=10, step=.10, value=3)
    def gui(self):
        self.option.observe(self.gui_calc.refresh, names='value')
        return self.option
class PARAM_IMG3:
    #sobel filter
    def __init__(self, GUI_CALC):
        self.gui_calc = GUI_CALC
        self.option=widgets.Dropdown(description='None',value=None)
    def gui(self):
        return widgets.VBox()

class GUI_CALC_EXPERIMENTAL:
    def __init__(self,project, msg=None):
        self.msg = msg
        self.par_img=[PARAM_IMG(self),PARAM_IMG2(self),PARAM_IMG3(self)]
        self.project = project
        self.data=[]

        calc_opt = widgets.Tab()
        calc_opt.set_title(0, 'brightness_filter')
        calc_opt.set_title(1, 'gaussian')
        calc_opt.set_title(2, 'sobel')

        calc_opt.children = [self.par_img[0].gui(),self.par_img[1].gui(), self.par_img[2].gui()]
        # calc_opt.selected_index = 0
        self.calc_opt = calc_opt

        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))

        self.job_type= widgets.Dropdown(
            options=["ImageJob"],
            value="ImageJob",
            description = "Job Type:"
        )
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

        self.mask = self.multi_checkbox_widget(self.data)
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

#   def set_gui_structure(self, gui_structure):
#       self.gui_structure = gui_structure
#       self.project = gui_structure.project
#       self.struc = gui_structure.structure
#       self.job_name.value = ""
#       self.refresh_job_name()

#       self.job = self.project.create_job(self.job_type, self.job_name.value)

    def refresh(self, job=None, *args):
        self.refresh_input()
        self.refresh_job_name()
        pass

    def _refresh_gui(self):
        #print('gui refresh!')
        job_box=None
        self.gui_box=None
        #job_box = widgets.VBox([self.filter_type, self.job_name,self.mask], layout={'border': '1px solid lightgray'})
        job_box = widgets.VBox([self.job_name,self.mask], layout={'border': '1px solid lightgray'})
        self.gui_box=widgets.HBox([widgets.VBox([self.calc_opt, job_box, self.create_btn, self.run_btn]), self.output])
        #return self.gui_box

    def refresh_job_name(self, *args):
        # self.output.clear_output()
        if self.job_name.value in self.project.list_nodes():
            job = self.project.load(self.job_name.value)
            self.set_job(job)
        else:
            self.run_btn.style.button_color = 'lightgreen'
            self.run_btn.description = 'Run'
            self.output.clear_output()

    def refresh_input(self, *args):
        if self.job_name.value == "":
            self.job_name.value = 'DummyJobNamePleaseChange'

        self.job = self.project.create_job(self.job_type.value, self.job_name.value)
        #if self.job.status == 'finished':
        #    self.set_job_params(self.job)
        #else:
        #    self.job.structure = self.struc
        #    self.potential.options = self.job.list_potentials()

    def refresh_mask(self,data_structure):
        #print('mask refresh!')
        self.data=data_structure.list_data()
        self.mask=None
        description=[]
        for datapath in self.data:
            description.append(os.path.split(datapath)[1])
        self.mask=self.multi_checkbox_widget(description)
        self._refresh_gui()

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
            mask=[w.value for w in self.mask.children]
            preview_mask=np.array([i for i, x in enumerate(mask) if x],dtype=int)
            #print(preview_mask)
            for image in self.data:
                self.job.add_image(image, as_gray=True,
               metadata={
                   'owner': 'Setareh Medghalchi',
                   'composition': 'Mg5Al3Ca',
                   'deformation': '2%'
               })
            self.set_param_img(preview_mask)
            self.job.run()
            self.refresh_job_name()
            plt.ioff()
            fig, ax = self.job.plot(mask=preview_mask, subplots_kwargs={'figsize': (20, 12)})
            with self.output:
                display(fig)
            self.msg.clear_output()
            with self.msg:
                print('finished')
        elif b.description == 'Delete':
            self.job.remove()
            self.job._status = None  # TODO: should be done by remove!
            self.refresh_job_name()

    def set_param_img(self,mask):
        idx=self.calc_opt.selected_index
        filter=self.calc_opt.get_title(idx)
        option=self.par_img[idx].option.value
        optiontitle=self.par_img[idx].option.description
        #print(filter,option,optiontitle)
        if filter=='gaussian':
            #print('set gaussin mask')
            self.job.images[(mask)].filters.gaussian(sigma=option)
        elif filter=='sobel':
           self.job.images[(mask)].filters.sobel()
        elif filter=='brightness_filter':
            pass
        else:
            print('?')

    def gui(self):
        #print('start gui', self)
        # self.job_type.observe(self.refresh, names='value')
        self.job_name.observe(self.refresh, names='value')
        self.mask.observe(self._refresh_gui, names='value')
        # self.potential.observe(self.refresh, names='value')

        self.create_btn.on_click(self.refresh)
        self.run_btn.on_click(self.on_run_btn_clicked)
        #job_box = widgets.VBox([self.filter_type, self.job_name,self.mask], layout={'border': '1px solid lightgray'})

        #self.gui_box=widgets.HBox([widgets.VBox([self.calc_opt, job_box, self.create_btn, self.run_btn]), self.output])
        self._refresh_gui()
        return self.gui_box

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
            options = ['Lammps', 'Vasp', ],
            value='Lammps',
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
        self.refresh_input()
        self.refresh_job_name()
        self.gui()
        return
        
    def refresh_job_name(self, *args):     
        # self.output.clear_output()    
        if self.job_name.value in self.project.list_nodes():
            job = self.project.load(self.job_name.value)
            self.set_job(job)
        else:
            try:
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
            except:
                return
            
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
        #print('start gui', self)
        # self.job_type.observe(self.refresh, names='value')
        self.job_name.observe(self.refresh, names='value')
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
        #print('start gui', self)
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
        # Values of the Atomistic pyiron as default
        self.gui_structure = GUI_Structure(project=self.project, msg=self.msg)
        self.gui_calcAtom = GUI_CALC_ATOMISTIC(msg=self.msg)
#       self.gui_input = self.gui_structure
        self.gui_calc = self.gui_calcAtom
        # Experimental tattile=['Data','Calculate','Explorer']
        self.gui_data = GUI_Data(project=self.project, msg=self.msg)
        self.gui_calcExp = GUI_CALC_EXPERIMENTAL(project=self.project,msg=self.msg)
        self.gui_explorer = GUI_EXPLORER(project)


    def on_clear_msg_clicked(self, b):
        self.msg.clear_output()

    def gui(self):
        #print('start gui', self)
        py_tab = widgets.Tab()
        py_tab.set_title(0, 'Atomistic')
        py_tab.set_title(1, 'Experimental'),
        py_tab.children = [self.gui_work_atom(), self.gui_work_exp()]

#       self.py_tab_children = [self.gui_work_atom,self.gui_work_exp]
#
#       def py_on_value_change(change):
#           sel_old = change['old']
#           sel_ind = change['new']
#           if sel_ind == 0:
#               print("set to atomistic")
#               self.tabtitle = ['Structure','Calculate','Explorer']
#               self.gui_input = self.gui_structure
#               self.gui_calc = self.gui_calcAtom
#           elif sel_ind == 1:
#               print("set to experimental")
#               self.tabtitle = ['Data', 'Calculate', 'Explorer']
#               self.gui_input = self.gui_data
#               self.gui_calc = self.gui_calcExp
#
#           self.msg.clear_output()
#           with self.msg:
#               print('sel: ', sel_old, sel_ind)
#               # print (sel_ind, type(tab.children[sel_ind]), hasattr(self.tab_children[sel_ind], 'refresh'))
#           self.py_tab_children[sel_ind].refresh()
#           self.tab_children.refresh()
#
#       py_tab.observe(py_on_value_change, names='selected_index')
        return widgets.VBox([py_tab, widgets.HBox([self.msg, self.clear_msg])], layout={'border': '4px solid lightgray'})

    def gui_work_atom(self):
        tabtitle=['Structure','Calculate','Explorer']
        tab = widgets.Tab()
        for tabidx in range(len(tabtitle)):
            tab.set_title(tabidx, tabtitle[tabidx])
        tab.children = [self.gui_structure.gui(), self.gui_calcAtom.gui(), self.gui_explorer.gui()]

        self.tab_children = [self.gui_structure, self.gui_calcAtom, self.gui_explorer]

        def on_value_change(change):
            #print('Atom_tab_chaged')
            sel_old = change['old']
            sel_ind = change['new']
            if sel_old == 0:
                self.gui_calc.set_gui_structure(self.gui_structure)
            elif (sel_old == 2 and self.gui_explorer.job != None):
                if hasattr(self.gui_explorer.job,"project"):
                    self.gui_calc.set_job(self.gui_explorer.job)
            self.msg.clear_output()
            #print('on change: self.tab_children[sel_ind]:',self.tab_children[sel_ind],sel_ind)
            with self.msg:
                print('sel: ', sel_old, sel_ind)
                # print (sel_ind, type(tab.children[sel_ind]), hasattr(self.tab_children[sel_ind], 'refresh'))
            self.tab_children[sel_ind].refresh()

        self.clear_msg.on_click(self.on_clear_msg_clicked)
        tab.observe(on_value_change, names='selected_index')
        return tab

    def gui_work_exp(self):
        tab = widgets.Tab()
        tabtitle=['Data','Calculate','Explorer']
        for tabidx in range(len(tabtitle)):
            tab.set_title(tabidx, tabtitle[tabidx])
        tab.children = [self.gui_data.gui(), self.gui_calcExp.gui(), self.gui_explorer.gui()]

        self.tab_children = [self.gui_data,self.gui_calcExp, self.gui_explorer]
        self.just_updated=False
        self.unset_just_updated=False

        def on_value_change(change):
            if self.just_updated:
                #print("just_updated")
                if self.unset_just_updated:
                    #print("reset just_updated")
                    self.just_updated = False
                    self.unset_just_updated = False
                    return
                self.unset_just_updated=True
                return
            #print('Exp_tab_chaged')
            sel_old = change['old']
            sel_ind = change['new']
#            if sel_old == 0:
#                self.gui_calcExp   .set_gui_input(self.gui_input)
            #el
            #if sel_old == 1:
            if sel_old == 0:
                self.gui_calcExp.refresh_mask(self.gui_data)
                tab.children = [self.gui_data.gui(), self.gui_calcExp.gui(), self.gui_explorer.gui()]
                self.tab_children = [self.gui_data,self.gui_calcExp, self.gui_explorer]
                tab.selected_index=sel_ind
            elif (sel_old == 2 and self.gui_explorer.job != None):
                if hasattr(self.gui_explorer.job, "project"):
                    self.gui_calcExp.set_job(self.gui_explorer.job)
            self.msg.clear_output()
            with self.msg:
                print ('sel: ', sel_old, sel_ind)
                # print (sel_ind, type(tab.children[sel_ind]), hasattr(self.tab_children[sel_ind], 'refresh'))
            self.tab_children[sel_ind].refresh()
            self.just_updated=True
            
        self.clear_msg.on_click(self.on_clear_msg_clicked)
        tab.observe(on_value_change, names='selected_index')
        return tab