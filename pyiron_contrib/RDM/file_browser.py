import os

import ipywidgets as widgets
from IPython.core.display import display

from pyiron_base import Project as BaseProject
from pyiron_contrib.generic.filedata import FileData, DisplayItem
from pyiron_contrib.project.project_browser import ProjectBrowser

class FileBrowser(ProjectBrowser):
    def __init__(self, project, Vbox=None, fix_path=False, show_files=True, proj_list=None, proj_info_list=None):
        """
            Filebrowser to browse the file system(s) of projects.
            Args:
                project : Any pyiron project.
                fix_path (bool): If True the path in the file system cannot be changed.
                show_files (bool): If True, files (project.list_files()) are shown.
                proj_list(list/None): List containing pyiron projects.
                proj_info_list(list/None): List of dictionaries containing additional information about the projects
                                           in the proj_list, has to be of same length. The dictionary is expected to
                                           have the following keys:
                                           "name": "A short name of the Project"
                                           "description": "A description of the Project \n to be displayed as tooltip"
        """
        self._proj_info_list = proj_info_list
        self._proj_list = proj_list
        self._proj_list_idx = None
        if proj_list is not None:
            for idx, pr in enumerate(proj_list):
                if project is pr:
                    self._proj_list_idx = idx
            if proj_info_list is not None and len(proj_list) != len(proj_info_list):
                raise ValueError("If provided proj_list and proj_info_list have to be of same length.")
            if self._proj_list_idx is None:
                self._proj_list_idx = 0
                self._proj_list = [project] + self._proj_list
                if self._proj_info_list is not None:
                    self._proj_info_list = [{"name": project.base_name,
                                         "description": str(type(project))+str(project)}].extend(self._proj_info_list)
        super().__init__(project=project, Vbox=Vbox, fix_path=fix_path, show_files=show_files)

    def _update_optionbox(self, optionbox):
        def gather_project_info(pr, pr_idx):
            if pr_idx == self._proj_list_idx:
                tooltip_local = "Filesystem of "
            else:
                tooltip_local = "Change to filesystem of "

            if self._proj_info_list is None:
                description_local = 'Project_' + str(pr_idx)
                tooltip_local += description_local
            else:
                description_local = self._proj_info_list[pr_idx]['name']
                tooltip_local = self._proj_info_list[pr_idx]['description']
            try:
                tooltip_local += ": \n" + str(pr) + "\n"
            except (ValueError, AttributeError):
                tooltip_local += '.'
            return [description_local, tooltip_local]

        checkbox_active_style = {"button_color": "#FF8888", 'font_weight': 'bold'}
        checkbox_inactive_style = {"button_color": "#CCAAAA"}
        super(FileBrowser, self)._update_optionbox(optionbox)
        if self._proj_list is None:
            return
        childs = []
        for idx, project in enumerate(self._proj_list):
            [description, tooltip] = gather_project_info(project, idx)
            button = widgets.Button(description=description, tooltip=tooltip,
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



