import os
from glob import iglob

import ipywidgets as widgets
from IPython import display as IPyDisplay
from IPython.core.display import display
from matplotlib import pylab as plt
import pandas

from pyiron_contrib.image.S3ObjectDB import S3ObjectDB
from pyiron_contrib.image.image import Image
from pyiron_contrib.image.measurement import MeasuredData


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
        elif filetype.lower() in ['.csv']:
            self.display_csv()
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
    def display_csv(self):
        with self.output:
            display(pandas.read_csv(self.path))
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


class FileBrowser(object):
    #ToDo:
    #       Make text-field searchable / autocomplete? .
    #       Use S3 store to search for data  -  for now: download data into tmp_dir which is rm after some time?
    #           Need upload method - upon choose files > upload them, ask for meta-data  >> Convert to own class <<
    #                                                                                   Needed for File upload to S3
    def __init__(self,project):
        self.project=project
        self.path = os.getcwd()
        self.data=[]
        self.box2_value=self.path
        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))
        self._clickedFiles=[]
        self.s3path=""
        # have a look at tempdir
        self.temp_dir=self.path+'/.Tempdir'
        self._data_access=S3ObjectDB(self.project,config_file="/home/nsiemer/pyiron/projects/config.json",group=self.s3path)
        self.path_storage=['','']
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
        self.box2=widgets.Text(description="(rel) Path",width='min-content')
        button=widgets.Button(description='Set Path', tooltip="Sets current path to provided string.")
        button2=widgets.Button(description="Choose File(s)",width='min-content',
                               tooltip='Loads currently activated files and all files '+
                                       'matching the provided string patten; wildcards allowed!')
        button3=widgets.Button(description="Reset selection",width='min-content')
        file_sys_button=widgets.Button(description='local',tooltip="Change to local filesystem",
                                       icon="fa-database",layout=widgets.Layout(width='80px'),
                                       style={'button_color': '#FF8888','font_weight': 'bold'})
        file_sys_button2=widgets.Button(description='RDM',tooltip="Change to Research Data Management System",
                                       icon="fa-database",layout=widgets.Layout(width='80px'),
                                       style={'button_color': '#FFAAAA'})
        def on_sys_change(b):
            if b.description == 'RDM':
                if self.data_sys=='S3':
                    return
                self._clickedFiles = []
                self.path_storage[0]=self.path
                self.path=self.path_storage[1]
                b.style.button_color='#FF8888'
                b.style.font_weight='bold'
                file_sys_button.style.button_color='#FFAAAA'
                file_sys_button.style.font_weight=''
                self.data_sys='S3'
                self._update_files()
                self._update(self.box)
                self.box2_value=self.path
                return
            if b.description == 'local':
                if self.data_sys=='local':
                    return
                self._clickedFiles = []
                self.path_storage[1]=self.path
                self.path=self.path_storage[0]
                b.style.button_color='#FF8888'
                b.style.font_weight='bold'
                file_sys_button2.style.button_color='#FFAAAA'
                file_sys_button2.style.font_weight=''
                self.data_sys='local'
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
                    self._download_and_choose()
                    return
                if len(self.box2.value) ==0:
                    path=self.path
                elif self.box2.value[0] != '/':
                    path=self.path+'/'+self.box2.value
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
        file_sys_button2.on_click(on_sys_change)
        return widgets.VBox([widgets.HBox([file_sys_button,file_sys_button2,self.box2,button,button2,button3]),
                             self.pathbox,widgets.HBox([self.box,self.output])])

    def list_data(self):
        return self.data

    # TODO: convert to get Data object and use this instead:
    # obj =  self._data_access.get(key)
    # data = obj['Body'].read()  the content of the Body is erased!
    # image = PIL.Image.open(io.BytesIO(data))
    # np_data = np.array(image)   < This may be handled by the image job class as input!
    def _download_and_choose(self):
        if len(self.box2.value) == 0:
            path = self.path
        elif self.box2.value[0] != '/':
            path = self.path + '/' + self.box2.value
        else:
            with self.output:
                print("Only relative paths supported")
        appendlist = []
        for f in self._data_access.glob(path):
            appendlist.append(f)
        for f in self._clickedFiles:
            appendlist.append(f)
        #appendlist has _full_ path in the bucket -> download from top directory.
        self._data_access.open("")
        objlist=[]
        for file in appendlist:
            objlist.append(self._data_access.get(file))
        self._data_access.download(appendlist,targetpath=self.temp_dir)
        self._data_access.close()
        for f in iglob(self.temp_dir+'/*'):
            self.data.append(f)

        with self.output:
            if len(appendlist) > 0:
                print('Loaded %i File(s):' % (len(appendlist)))
                for i in appendlist:
                    print(i)
            else:
                print('No files chosen')

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
                Display_file(f, self.output)
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


class GUI_Data:
    def __init__(self,project,msg=None):
        self.project = project
        self.filewidget= FileBrowser(self.project)
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