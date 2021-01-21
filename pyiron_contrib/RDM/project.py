import os
import posixpath

from pyiron_base import InputList, ProjectHDFio
from pyiron_base.project.path import GenericPath
from pyiron_contrib.generic.filedata import DisplayItem
from pyiron_contrib.project.project import Project as ProjectCore


class Project(ProjectCore):

    """ Basically a wrapper of a generic Project to extend for metadata. """
    def __init__(self, path="", user=None, sql_query=None, default_working_directory=False):
        super().__init__(path=path,
                         user=user,
                         sql_query=sql_query,
                         default_working_directory=default_working_directory
                         )
        self._project_info = InputList(table_name="projectinfo")
        self._metadata = InputList(table_name="metadata")
        self.hdf5 = self.create_hdf(self.path, self.base_name + "_projectdata")
        self.load_metadata()
        self._load_projectinfo()
    __init__.__doc__ = ProjectCore.__init__.__doc__

    def open_RDM_GUI(self):
        from pyiron_contrib.RDM.RDM_gui import GUI_RDM
        return GUI_RDM(project=self).gui()

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, metadata):
        self._metadata = InputList(metadata, table_name="metadata")

    def save_metadata(self):
        self._metadata.to_hdf(self.hdf5, group_name=None)

    def load_metadata(self):
        try:
            self._metadata.from_hdf(self.hdf5, group_name=None)
        except ValueError:
            pass

    @property
    def project_info(self):
        return self._project_info

    @project_info.setter
    def project_info(self, project_info):
        self._project_info = InputList(project_info, table_name="projectinfo")

    def _save_projectinfo(self):
        self._project_info.to_hdf(self.hdf5, group_name=None)

    def _load_projectinfo(self):
        try:
            self._project_info.from_hdf(self.hdf5, group_name=None)
        except ValueError:
            pass

    def open(self, rel_path, history=True):
        new = super().open(rel_path, history=history)
        new.hdf5 = new.create_hdf(new.path, new.base_name + "_projectdata")
        new._metadata = InputList(table_name="metadata")
        new._project_info = InputList(table_name="projectinfo")
        new.load_metadata()
        new._load_projectinfo()
        return new


class FileBrowseProject(GenericPath):
    def __init__(self, path="/"):
        path = self._convert_str_to_abs_path(path)
        self.hdf_as_dirs = False
        super().__init__(root_path='/', project_path=path)
        if not os.path.isdir(self.path):
            raise ValueError("Path {} is not a directory and {} does not create new directories."
                             .format(path, self.__class__))

    def copy(self):
        """
        copy of the current FileBrowseProject

        Returns:
            FileBrowseProject:
        """
        new = self.__class__(path=self.path)
        new.hdf_as_dirs = self.hdf_as_dirs
        return new

    def _convert_str_to_abs_path(self, path):
        """
        Convert path in string representation to an GenericPath object

        Args:
            path (str): path

        Returns:
            str: absolute path
        """
        if isinstance(path, GenericPath):
            return path.path
        elif isinstance(path, str):
            path = os.path.normpath(path)
            if not os.path.isabs(path):
                path_local = self._windows_path_to_unix_path(
                    posixpath.abspath(os.curdir)
                )
                path = posixpath.join(path_local, path)
            return_path = self._windows_path_to_unix_path(path)
            return return_path
        else:
            raise TypeError("Only string and GenericPath objects are supported.")

    def listdir(self):
        """
        equivalent to os.listdir
        list all files and directories in this path

        Returns:
            list: list of folders and files in the current project path
        """
        try:
            return os.listdir(self.path)
        except OSError:
            return []

    def open(self, path):
        if os.path.isabs(path):
            new = self.__class__(path)
        else:
            new = self.__class__(self.path)
            new.project_path = posixpath.normpath(posixpath.join(self.project_path, path))
        new.hdf_as_dirs = self.hdf_as_dirs
        return new

    def list_nodes(self):
        """ List all files in the current directory. """
        file_list = []
        for f in self.listdir():
            if os.path.isfile(os.path.join(self.path, f)):
                if not (self.hdf_as_dirs and os.path.splitext(f)[1] == ".h5"):
                    file_list.append(f)
        return file_list

    def list_groups(self):
        """ List all directories in the current directory. """
        group_list = []
        for f in self.listdir():
            if os.path.isdir(os.path.join(self.path, f)):
                group_list.append(f)
            if self.hdf_as_dirs and os.path.isfile(os.path.join(self.path, f)) and os.path.splitext(f)[1] == ".h5":
                group_list.append(f)
        return group_list

    def __getitem__(self, item):
        """
        Get item from project

        Args:
            item (str, int): key

        Returns:
            Project, GenericJob, JobCore, dict, list, float: basically any kind of item inside the project.
        """
        if isinstance(item, slice):
            raise NotImplementedError("Implement if needed, e.g. for [:]")
        else:
            item_lst = [sub_item.replace(" ", "") for sub_item in item.split("/")]
            if len(item_lst) > 1:
                return self._get_item_helper(
                    item=item_lst[0], convert_to_object=True
                ).__getitem__("/".join(item_lst[1:]))
        return self._get_item_helper(item=item, convert_to_object=True)

    def _get_item_helper(self, item, convert_to_object=True):
        """
        Internal helper function to get item from project

        Args:
            item (str, int): key
        Returns:
            Project, GenericJob, JobCore, dict, list, float: basically any kind of item inside the project.
        """
        if item == "..":
            return self.open(item)
        if item in self.list_nodes():
            file_name = posixpath.join(self.path, "{}".format(item))
            if os.path.splitext(file_name)[1] == '.h5':
                return ProjectHDFio(project=self, file_name=file_name)
            return DisplayItem(file_name).display()
        if item in self.list_groups():
            file_name = posixpath.join(self.path, "{}".format(item))
            if os.path.isfile(file_name) and os.path.splitext(file_name)[1] == '.h5':
                return ProjectHDFio(project=self, file_name=file_name)
            return self.open(item)
        raise ValueError("Unknown item: {}".format(item))

    def __repr__(self):
        """
        Human readable string representation of the project object

        Returns:
            str: string representation
        """
        return str(
            {"groups": self.list_groups(), "nodes": self.list_nodes()}
        )
