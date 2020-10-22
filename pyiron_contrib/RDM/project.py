from pyiron_base import Project as ProjectCore, InputList

class Project(ProjectCore):
    """
    Basically a wrapper of Project from pyiron_base to extend for metadata
    """
    def __init__(self, path="", user=None, sql_query=None, default_working_directory=False):
        super().__init__(path=path,
                         user=user,
                         sql_query=sql_query,
                         default_working_directory=default_working_directory
                         )
        self._metadata = InputList(table_name="metadata")
        self.hdf5 = self.create_hdf(self.path, self.base_name + "_projectdata")
        self.load_metadata()

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

    def copy(self):
        """
        Copy the project object - copying just the Python object but maintaining the same pyiron path

        Returns:
            Project: copy of the project object
        """
        new = Project(path=self.path, user=self.user, sql_query=self.sql_query)
        return new

    def open(self, rel_path, history=True):
        new = super().open(rel_path, history=history)
        new.hdf5 = new.create_hdf(new.path, new.base_name + "_projectdata")
        new._metadata = InputList(table_name="metadata")
        new.load_metadata()
        return new
