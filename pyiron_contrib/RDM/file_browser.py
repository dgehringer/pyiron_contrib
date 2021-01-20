import os

import ipywidgets as widgets
from IPython.core.display import display

from pyiron_base import Project as BaseProject
from pyiron_contrib.generic.filedata import FileData, DisplayItem
from pyiron_contrib.project.project_browser import ProjectBrowser

class FileBrowser(ProjectBrowser):
    def __init__(self, project, Vbox=None, fix_path=False, show_files=True, proj_list=None):
        self._proj_list = proj_list
        if proj_list is not None:
            for idx, pr in enumerate(proj_list):
                if project is pr:
                    self._proj_list_idx = idx
        super().__init__(project=project, Vbox=Vbox, fix_path=fix_path, show_files=show_files)

    def _update_optionbox(self, optionbox):
        checkbox_active_style = {"button_color": "#FF8888", 'font_weight': 'bold'}
        checkbox_inactive_style = {"button_color": "#CCAAAA"}
        super(FileBrowser, self)._update_optionbox(optionbox)
        if self._proj_list is None:
            return
        childs = []
        for idx, project in enumerate(self._proj_list):
            description = 'Project_'+str(idx)
            button = widgets.Button(description=description, tooltip="Change to filesystem of "+description,
                                    icon="database", layout=widgets.Layout(width='80px'))
            if idx == self._proj_list_idx:
                button.style = checkbox_active_style
            else:
                button.style = checkbox_inactive_style
            button.project_idx = idx
            button.on_click(self._switch_project)
            childs.append(button)
        childs.extend(list(optionbox.children))
        optionbox.children = tuple(childs)

    def _switch_project(self, b):
        self.output.clear_output(True)
        self._proj_list[self._proj_list_idx] = self.project.copy()
        self.project = self._proj_list[b.project_idx]
        self._proj_list_idx = b.project_idx
        self._node_as_dirs = isinstance(self.project, BaseProject)
        self.update()



