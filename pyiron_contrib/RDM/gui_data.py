import os
from glob import iglob

import ipywidgets as widgets
from IPython import display as IPyDisplay
from IPython.core.display import display
from matplotlib import pylab as plt
import pandas

from pyiron_contrib.RDM.S3ObjectDB import S3ObjectDB
from pyiron_contrib.image.image import Image
from pyiron_contrib.RDM.measurement import MeasuredData


class DisplayFile:
    """
        Class to display a file localted at path in the given outwidget
    """
    # TODO:
    '''
/home/nsiemer/pyiron.git/pyiron_contrib/pyiron_contrib/image/image.py:259: RuntimeWarning: More than 20 figures have been opened.
 Figures created through the pyplot interface (`matplotlib.pyplot.figure`) are retained until explicitly closed and may consume too much memory. 
 (To control this warning, see the rcParam `figure.max_open_warning`).
  fig, ax = plt.subplots(**subplots_kwargs)
    '''

    def __init__(self, path, outwidget):
        self.path = path
        self.output = outwidget
        _, filetype = os.path.splitext(path)
        if filetype.lower() in ['.tif', '.tiff']:
            self.display_tiff()
        elif filetype.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
            self.display_img()
        elif filetype.lower() in ['.txt']:
            self.display_txt()
        elif filetype.lower() in ['.csv']:
            self.display_csv()
        else:
            self.diplay_default()

    def display_tiff(self):
        plt.ioff()
        img = Image(self.path)
        fig, ax = img.plot()
        with self.output:
            display(fig)

    def display_txt(self):
        with self.output:
            with open(self.path) as f:
                print(f.read(), end='')

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


class DisplayMetadata:
    def __init__(self, metadata, outwidget):
        self.metadata = metadata
        self.output = outwidget
        self.display()

    def display(self):
        with self.output:
            print("Metadata:")
            print("------------------------")
            for key, value in self.metadata.items():
                print(key + ': ' + value)


class FileBrowser(object):
    """
        File Browser Widget with S3 support

        Allows to browse files in the local or a remote S3 based file system.
        Selected files may be received from this FileBrowser widget by its get_data method.
    """

    # ToDo:
    #           Need upload method - upon choose files > upload them, ask for meta-data  >> Convert to own class <<
    #                                                                                   Needed for File upload to S3
    def __init__(self,
                 Vbox=None,
                 s3path="",
                 fix_s3_path=False,
                 storage_system="local",
                 fix_storage_sys=False,
                 S3_config_file=None
                 ):
        """
            Filebrowser to browse the local or a remote (S3-based) file system.
            Args:
              s3path (str): Starting path within the remote file system.
              fix_s3_path (bool): If True the path in the remote file system cannot be changed.
              storage_system (str): The filesystem to access (fist) either "local" or "S3".
              fix_storage_sys (bool): If True the file system cannot be changed.
              S3_config_file (str): path to a json configuration file with login credentials for the remote file system.
        """
        if Vbox is None:
            self.box = widgets.VBox()
        else:
            self.box = Vbox
        self.fix_s3_path = fix_s3_path
        self.s3path = s3path
        self.data_sys = storage_system
        if self.data_sys == "local":
            self.path = os.getcwd()
        else:
            self.path = self.s3path
        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))
        self._clickedFiles = []
        self.data = []
        self.fix_storage_sys = fix_storage_sys
        self._data_access = S3ObjectDB(config_file=S3_config_file,
                                       group=self.s3path)
        self.path_storage = [os.getcwd(), self.s3path]
        self._update_files()
        self.pathbox = widgets.HBox(layout=widgets.Layout(width='100%', justify_content='flex-start'))
        self.optionbox = widgets.HBox()
        self.filebox = widgets.VBox(layout=widgets.Layout(width='50%', height='100%', justify_content='flex-start'))
        self.path_string_box = widgets.Text(description="(rel) Path", width='min-content')
        self.update()

    def configure(self,
                 s3path=None,
                 fix_s3_path=None,
                 storage_system=None,
                 fix_storage_sys=None,
                 ):
        """
            Reconfigure and refresh Filebrowser.
            Args:
              s3path (str/None): Path within the remote file system.
              fix_s3_path (bool): If True the path in the remote file system cannot be changed.
              storage_system (str/None): The filesystem to access (first): either "local" or "S3".
              fix_storage_sys (bool): If True the file system cannot be changed.
        """
        if s3path is not None:
            self.s3path = s3path
        if fix_s3_path is not None:
            self.fix_s3_path = fix_s3_path
        if storage_system is not None:
            if storage_system == "S3" and self.data_sys == "local":
                self.path_storage[0] = self.path
                self.path = self.path_storage[1]
            elif storage_system == "local" and self.data_sys == "S3":
                self.path_storage[1] = self.path
                self.path = self.path_storage[0]
            self.data_sys = storage_system
        if fix_storage_sys is not None:
            self.fix_storage_sys = fix_storage_sys

        if s3path is not None:
            if self.data_sys == "S3":
                self.path = self.s3path
            else:
                self.path_storage[1] = self.s3path
        self._update_files()
        self.update()

    def _update_files(self):
        self.files = list()
        self.dirs = list()
        if self.data_sys == "local":
            if os.path.isdir(self.path):
                for f in iglob(self.path + '/*'):
                    if os.path.isdir(f):
                        self.dirs.append(os.path.split(f)[1])
                    else:
                        self.files.append(os.path.split(f)[1])
        else:
            self._data_access.open(self.path)
            self.files = self._data_access.list_nodes()
            if not self.fix_s3_path:
                self.dirs = self._data_access.list_groups()

    def gui(self):
        self.update()
        return self.box

    def update(self, Vbox=None):
        if Vbox is None:
            Vbox = self.box
        self._update_files()
        #self._update_pathbox(self.pathbox)
        self._update_optionbox(self.optionbox)
        self._update_filebox(self.filebox)
        body = widgets.HBox([self.filebox, self.output],
                            layout=widgets.Layout(
                                min_height='100px',
                                max_height='800px'
                            ))
        Vbox.children = tuple([self.optionbox, self.pathbox, body])

    def _update_optionbox(self, optionbox):
        def on_sys_change(b):
            if b.description == 'RDM':
                if self.data_sys == 'S3':
                    return
                self._clickedFiles = []
                self.path_storage[0] = self.path
                self.path = self.path_storage[1]
                b.style = checkbox_active_style
                file_sys_button_local.style = checkbox_inactive_style
                if self.fix_s3_path:
                    set_path_button.disabled = True
                self.data_sys = 'S3'
                self._update_files()
                self._update_filebox(self.filebox)
                return
            if b.description == 'local':
                if self.data_sys == 'local':
                    return
                self._clickedFiles = []
                self.path_storage[1] = self.path
                self.path = self.path_storage[0]
                b.style = checkbox_active_style
                set_path_button.disabled = False
                file_sys_button_S3.style = checkbox_inactive_style
                self.data_sys = 'local'
                self._update_files()
                self._update_filebox(self.filebox)
                return
        # some color definitions:
        checkbox_active_style = {"button_color": "#FF8888", 'font_weight': 'bold'}
        checkbox_inactive_style = {"button_color": "#CCAAAA"}

        file_sys_button_local = widgets.Button(description='local', tooltip="Change to local filesystem",
                                         icon="fa-database", layout=widgets.Layout(width='80px'))
        file_sys_button_S3 = widgets.Button(description='RDM', tooltip="Change to Research Data Management System",
                                          icon="fa-database", layout=widgets.Layout(width='80px'))
        if self.data_sys == "local":
            file_sys_button_local.style = checkbox_active_style
            file_sys_button_S3.style = checkbox_inactive_style
        else:
            file_sys_button_local.style = checkbox_inactive_style
            file_sys_button_S3.style = checkbox_active_style

        file_sys_button_local.on_click(on_sys_change)
        file_sys_button_S3.on_click(on_sys_change)

        if self.fix_storage_sys:
            if self.data_sys == "local":
                childs = [file_sys_button_local,  self.path_string_box]
            else:
                childs = [file_sys_button_S3,  self.path_string_box]
        else:
            childs = [file_sys_button_local, file_sys_button_S3, self.path_string_box]

        set_path_button = widgets.Button(description='Set Path', tooltip="Sets current path to provided string.")
        set_path_button.on_click(self._click_option_button)
        if self.fix_s3_path and self.data_sys == "S3":
            set_path_button.disabled = True
        if not (self.fix_s3_path and self.fix_storage_sys and self.data_sys == "S3"):
            childs.append(set_path_button)
        button = widgets.Button(description="Select File(s)", width='min-content',
                                 tooltip='Selects all files ' +
                                         'matching the provided string patten; wildcards allowed.')
        button.on_click(self._click_option_button)
        childs.append(button)
        button = widgets.Button(description="Reset selection", width='min-content')
        button.on_click(self._click_option_button)
        childs.append(button)

        optionbox.children = tuple(childs)

    def _click_option_button(self, b):
        self.output.clear_output(True)
        with self.output:
            print('')
        if b.description == 'Set Path':
            if self.data_sys == 'S3':
                if self.fix_s3_path:
                    return
                path = '/' + self.path
            else:
                path = self.path
            if len(self.path_string_box.value) == 0:
                with self.output:
                    print('No path given')
                return
            elif self.path_string_box.value[0] != '/':
                path = path + '/' + self.path_string_box.value
            else:
                path = self.path_string_box.value
            # check path consistency:
            if (self.data_sys == 'local' and os.path.exists(path)):
                self.path = os.path.abspath(path)
            elif (self._data_access.is_dir(path[1:]) and self.data_sys == 'S3'):
                self.path = path[1:]
            else:
                self.path_string_box.__init__(description="(rel) Path", value='')
                with self.output:
                    print('No valid path')
                return
            self._update_files()
            self._update_filebox(self.filebox)
            self.path_string_box.__init__(description="(rel) Path", value='')
        if b.description == 'Choose File(s)':
            self._select_files()
        if b.description == 'Reset selection':
            self._clickedFiles = []
            self._update_filebox(self.filebox)

    def get_data(self):
        if self.data_sys == "S3":
            self._download_data_from_s3()
        else:
            for file in self._clickedFiles:
                data = MeasuredData(source=file)
                self.data.append(data)
        with self.output:
            if len(self.data) > 0:
                print('Loaded %i File(s):' % (len(self.data)))
                for i in self.data:
                    print(i.filename)
            else:
                print('No files chosen')
        self._clickedFiles = []
        self._update_filebox(self.filebox)
        return self.data

    def put_data(self, data, metadata=None):
        """
        Uploads a single data object to the current directory of the RDM System
        Args:
            data: MeasuredData Object like the ones stored in self.data
            metadata: metadata to be used (has to be a dictionary of type {"string": "string, })
                      provided metadata overwrites the one possibly present in the data object
        """
        self._data_access.put(data, metadata)

    def _download_data_from_s3(self):
        for file in self._clickedFiles:
            filename = os.path.split(file)[1]
            filetype = os.path.splitext(filename)[1]
            if len(filetype[1:]) == 0:
                filetype = None
            else:
                filetype = filetype[1:]
            obj = self._data_access.get(file, abspath=True)
            data = MeasuredData(data=obj['Body'].read(), filename=filename, filetype=filetype,
                                metadata=obj["Metadata"])
            self.data.append(data)

    def upload_data_to_s3(self, files, metadata=None):
        """
        Uploads files into the currently opened directory of the Research Data System
        Arguments:
            files `list` : List of filenames to upload
            metadata `dictionary`: metadata of the files (Not nested, only "str" type)
        """
        self._data_access.upload(files=files, metadata=metadata)

    def _select_files(self):
        if len(self.path_string_box.value) == 0:
            path = self.path
        elif self.path_string_box.value[0] != '/':
            path = self.path + '/' + self.path_string_box.value
        elif self.data_sys == "S3":
            with self.output:
                print("Only relative paths supported")
            return
        else:
            path = self.path_string_box.value
        appendlist = []
        if self.data_sys == "local":
            for f in iglob(path):
                if os.path.isfile(f):
                    appendlist.append(f)
        else:
            appendlist = self._data_access.glob(path)
        self._clickedFiles.extend(appendlist)
        self._update_filebox(self.filebox)
        with self.output:
            if len(appendlist) > 0:
                print('Selected %i File(s):' % (len(appendlist)))
                for i in appendlist:
                    print(i)
            else:
                print('No additional files selected')

    def _update_pathbox(self, box):
        path_color = '#DDDDAA'
        home_color = '#999999'

        def on_click(b):
            self.path = b.path
            self._update_files()
            self._update_filebox(self.filebox)
            self.path_string_box.__init__(description="(rel) Path", value='')

        buttons = []
        tmppath = self.path
        tmppath_old = self.path + '/'
        while tmppath != tmppath_old:
            tmppath_old = tmppath
            [tmppath, dir] = os.path.split(tmppath)
            button = widgets.Button(description=dir + '/', layout=widgets.Layout(width='auto'))
            button.style.button_color = path_color
            button.path = tmppath_old
            button.on_click(on_click)
            if self.fix_s3_path and self.data_sys == "S3":
                button.disabled = True
            buttons.append(button)
        button = widgets.Button(icon="fa-home", layout=widgets.Layout(width='auto'))
        button.style.button_color = home_color
        if self.data_sys == 'local':
            button.path = os.getcwd()
        else:
            button.path = self.s3path
            if self.fix_s3_path:
                button.disabled = True
        button.on_click(on_click)
        buttons.append(button)
        buttons.reverse()
        box.children = tuple(buttons)

    def _update_filebox(self, filebox):
        # color definitions
        dir_color = '#9999FF'
        file_chosen_color = '#FFBBBB'
        file_color = '#DDDDDD'
        self.output.clear_output(True)

        def on_click(b):
            self.path = os.path.join(self.path, b.description)
            self._update_files()
            self._update_filebox(filebox)

        def on_click_file(b):
            f = os.path.join(self.path, b.description)
            self.output.clear_output(True)
            if self.data_sys == 'local':
                DisplayFile(f, self.output)
            else:
                metadata = self._data_access.get_metadata(f, abspath=True)
                DisplayMetadata(metadata, self.output)
            if f in self._clickedFiles:
                b.style.button_color = file_color
                self._clickedFiles.remove(f)
            else:
                b.style.button_color = file_chosen_color
                self._clickedFiles.append(f)

        buttons = []
        item_layout = widgets.Layout(width='80%',
                                     height='30px',
                                     min_height='24px',
                                     display='flex',
                                     align_items="center",
                                     justify_content='flex-start')
        for f in self.dirs:
            button = widgets.Button(description=f,
                                    icon="fa-folder",
                                    layout=item_layout)
            button.style.button_color = dir_color
            button.on_click(on_click)
            buttons.append(button)
        for f in self.files:
            button = widgets.Button(description=f,
                                    icon="fa-file-o",
                                    layout=item_layout)
            if os.path.join(self.path, f) in self._clickedFiles:
                button.style.button_color = file_chosen_color
            else:
                button.style.button_color = file_color
            button.on_click(on_click_file)
            buttons.append(button)
        filebox.children = tuple(buttons)
        self._update_pathbox(self.pathbox)


class GUI_Data:
    def __init__(self, project, msg=None):
        self.project = project
        self.filewidget = FileBrowser()
        self.msg = msg

    def refresh(self):
        pass

    def _get_data(self):
        self.data = self.filewidget.get_data()

    def list_data(self):
        self._get_data()
        return self.data

    def gui(self):
        # print('start gui', self)
        self.filebrws = self.filewidget.gui()
        #       self.data_name = widgets.Text(
        #           value='',
        #           placeholder='Type something',
        #           description='File Name:',
        #           disabled=False
        #       )
        return self.filebrws
