import os

import ipywidgets as widgets
from IPython.core.display import display

from pyiron_base import Project as BaseProject
from pyiron_contrib.generic.data import Data
from pyiron_contrib.generic.display_item import DisplayItem


class ProjectBrowser:
    """
        File Browser Widget with S3 support

        Allows to browse files in the local or a remote S3 based file system.
        Selected files may be received from this FileBrowser widget by data attribute.
    """
    def __init__(self,
                 project,
                 Vbox=None,
                 fix_path=False,
                 show_files=True
                 ):
        """
            Filebrowser to browse the project file system.
            Args:
                project (:class:`pyiron.Project`):
                fix_path (bool): If True the path in the file system cannot be changed.
        """
        self.project = project.copy()
        self._node_as_dirs = isinstance(self.project, BaseProject)
        self._initial_path = self.path
        self._project_root_path = self.project.root_path

        if Vbox is None:
            self.box = widgets.VBox()
        else:
            self.box = Vbox
        self.fix_path = fix_path
        self._busy = False
        self._show_files = show_files
        self.output = widgets.Output(layout=widgets.Layout(width='50%', height='100%'))
        #TODO: move to project self._display_file = DisplayFile(file=None, outwidget=self.output).display_file
        #TODO: move to project self._display_metadata = DisplayMetadata(metadata=None, outwidget=self.output).display
        self._clickedFiles = []
        self._data = None
        self.pathbox = widgets.HBox(layout=widgets.Layout(width='100%', justify_content='flex-start'))
        self.optionbox = widgets.HBox()
        self.filebox = widgets.VBox(layout=widgets.Layout(width='50%', height='100%', justify_content='flex-start'))
        self.path_string_box = widgets.Text(description="(rel) Path", width='min-content')
        self._display_item = DisplayItem(item=None, outwidget=self.output).display
        self.update()

    @property
    def path(self):
        return self.project.path

    def _busy_check(self, busy=True):
        if self._busy and busy:
            return
        else:
            self._busy = busy

    def _update_files(self):
        # HDF and S3 project do not have list_files
        self.files = list()
        if self._show_files:
            try:
                self.files = self.project.list_files()
            except AttributeError:
                pass
        self.nodes = self.project.list_nodes()
        self.dirs = self.project.list_groups()

    def gui(self):
        self.update()
        return self.box

    def update(self, Vbox=None, fix_path = None, show_files=None):
        if Vbox is None:
            Vbox = self.box
        if fix_path is not None:
            self.fix_path = fix_path
        if show_files is not None:
            self._show_files = show_files
        self.output.clear_output(True)
        self._update_files()
        self._update_optionbox(self.optionbox)
        self._update_filebox(self.filebox)
        self._update_pathbox(self.pathbox)
        body = widgets.HBox([self.filebox, self.output],
                            layout=widgets.Layout(
                                min_height='100px',
                                max_height='800px'
                            ))
        Vbox.children = tuple([self.optionbox, self.pathbox, body])

    def _update_optionbox(self, optionbox):

        set_path_button = widgets.Button(description='Set Path', tooltip="Sets current path to provided string.")
        set_path_button.on_click(self._click_option_button)
        if self.fix_path:
            set_path_button.disabled = True
        childs = [set_path_button, self.path_string_box]

        #button = widgets.Button(description="Select File(s)", width='min-content',
        #                         tooltip='Selects all files ' +
        #                                 'matching the provided string patten; wildcards allowed.')
        #button.on_click(self._click_option_button)
        #childs.append(button)
        button = widgets.Button(description="Reset selection", width='min-content')
        button.on_click(self._click_option_button)
        childs.append(button)

        optionbox.children = tuple(childs)

    def _click_option_button(self, b):
        self._busy_check()
        self.output.clear_output(True)
        with self.output:
            print('')
        if b.description == 'Set Path':
            if self.fix_path:
                return
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
            self._update_project(path)
        if b.description == 'Reset selection':
            self._clickedFiles = []
            self._data = None
            self._update_filebox(self.filebox)
        self._busy_check(False)

    #@property
    #def data(self):
    #    for file in self._clickedFiles:
    #        data = Data(source=file)
    #        self._data.append(data)
    #    with self.output:
    #        if len(self._data) > 0:
    #            print('Loaded %i File(s):' % (len(self._data)))
    #            for i in self._data:
    #                print(i.filename)
    #        else:
    #            print('No files chosen')
    #    self._clickedFiles = []
    #    self._update_filebox(self.filebox)
    #    return self._data

    def _update_project_worker(self, rel_path):
        try:
            new_project = self.project[rel_path]
        except ValueError:
            self.path_string_box.__init__(description="(rel) Path", value='')
            return "No valid path"
        else:
            if new_project is not None:
                self.project = new_project

    def _update_project(self, path):
        self.output.clear_output(True)
        # check path consistency:
        rel_path = os.path.relpath(path, self.path)
        if rel_path == '.':
            return
        self._update_project_worker(rel_path)
        self._node_as_dirs = isinstance(self.project, BaseProject)
        self._update_files()
        self._update_filebox(self.filebox)
        self._update_pathbox(self.pathbox)
        self.path_string_box.__init__(description="(rel) Path", value='')

    def _update_pathbox(self, box):
        path_color = '#DDDDAA'
        h5_path_color = '#CCCCAA'
        home_color = '#999999'

        def on_click(b):
            self._busy_check()
            self._update_project(b.path)
            self._busy_check(False)

        #with self.output:
        #    display(self.project)
        buttons = []
        tmppath = os.path.abspath(self.path)
        if tmppath[-1] == '/':
            tmppath = tmppath[:-1]
        len_root_path = len(os.path.split(self._project_root_path[:-1])[0])
        tmppath_old = tmppath + '/'
        while tmppath != tmppath_old:
            tmppath_old = tmppath
            [tmppath, curentdir] = os.path.split(tmppath)
            button = widgets.Button(description=curentdir + '/', layout=widgets.Layout(width='auto'))
            button.style.button_color = path_color
            button.path = tmppath_old
            button.on_click(on_click)
            if self.fix_path or len(tmppath) < len_root_path - 1:
                button.disabled = True
            buttons.append(button)
        button = widgets.Button(icon="fa-home", layout=widgets.Layout(width='auto'))
        button.style.button_color = home_color
        button.path = self._initial_path
        if self.fix_path:
            button.disabled = True
        button.on_click(on_click)
        buttons.append(button)
        buttons.reverse()
        box.children = tuple(buttons)

    def _update_filebox(self, filebox):
        # color definitions
        dir_color = '#9999FF'
        node_color = '#9999EE'
        file_chosen_color = '#FFBBBB'
        file_color = '#DDDDDD'

        if self._node_as_dirs:
            dirs = self.dirs + self.nodes
            files = self.files
        else:
            files = self.nodes + self.files
            dirs = self.dirs

        def on_click_group(b):
            self._busy_check()
            path = os.path.join(self.path, b.description)
            self._update_project(path)
            self._busy_check(False)

        def on_click_file(b):
            self._busy_check()
            f = os.path.join(self.path, b.description)
            self.output.clear_output(True)
            try:
                with self.output:
                    display(self.project.display_item(b.description))
            except:
                try:
                    self._display_item(self.project[b.description])
                except:
                    with self.output:
                        print([b.description])
            if f in self._clickedFiles:
                self._data = None
                b.style.button_color = file_color
                self._clickedFiles.remove(f)
            else:
                try:
                    data = self.project[b.description]
                except:
                    pass
                else:
                    self._data = Data(data=data, filename=b.description, metadata={"path": f})
                b.style.button_color = file_chosen_color
                #self._clickedFiles.append(f)
                self._clickedFiles = [f]
                self._update_filebox(filebox)
            self._busy_check(False)

        buttons = []
        item_layout = widgets.Layout(width='80%',
                                     height='30px',
                                     min_height='24px',
                                     display='flex',
                                     align_items="center",
                                     justify_content='flex-start')

        for f in dirs:
            button = widgets.Button(description=f,
                                    icon="fa-folder",
                                    layout=item_layout)
            button.style.button_color = dir_color
            button.on_click(on_click_group)
            buttons.append(button)

        for f in files:
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

