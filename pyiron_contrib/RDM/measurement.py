from datetime import datetime
import os
import io
from PIL import Image
import numpy as np

from pyiron_base.job.core import JobCore
from pyiron_base.settings.generic import Settings

s = Settings()


class MeasuredData:
    """
    Measured Data stores an instance of a measurement, e.g. a single Image.
    """
    def __init__(self, source=None, data=None, filename=None, metadata=None, filetype=None, storedata=False):
        if (source is None) and (data is None):
            raise ValueError("No data given")
        if data is None:
            self.hasdata = False
        else:
            self.hasdata = True
            self._data = data
        self.measurement = None
        if source is not None:
            self.filename = os.path.split(source)[1]
            self.source = source
        elif filename is None:
            raise ValueError("No filename given")
        else:
            self.filename = filename
        if (filetype is None) and (self.filename is not None):
            filetype = os.path.splitext(self.filename)[1]
            if len(filetype[1:]) == 0:
                self.filetype = None
            else:
                self.filetype = filetype[1:]
        else:
            self.filetype = filetype
        if storedata and data is None:
            self._data = self._read_source()
        self.metadata = metadata

    def _read_source(self):
        with open(self.source, "rb") as f:
            content = f.read()
        return content

    def data(self):
        if self.hasdata:
            return self._data
        else:
            self._read_source()

    def data_as_np_array(self):
        """
        returns the data converted to a numpy array if convergence is known for the given filetype.
        Otherwise behave as data()
        """
        if not self.hasdata:
            return self.source
        if self.filetype.upper() in ["TIF", "TIFF"]:
            return np.array(Image.open(io.BytesIO(self._data)))
        self.data()

    def __repr__(self):
        return "pyiron-MeasuredData containing " + self.filename

class Measurement(JobCore):
    """
    The Measurement contains data from an experiment along with its metadata.
    Idea: Have this as main class to represent a measurement collecting several measured entities
        --> E.g. data from one session using the same sample
    """
    def __init__(self, project, job_name):
        super().__init__(project, job_name)
        self.__name__ = "Measurement"
        self._type = None
        self.sample = None
        self._metadata = None
        self._data = []

    @property
    def type(self):
        """
        Get the type of data associated with the Measurement, e.g. TIFF file
        """
        return self._type

    @type.setter
    def type(self, type):
        self._type = type

    @property
    def data(self):
        """
        Get the data associated with the Measurement in an appropriate format
        """
        return self._data

    @data.setter
    def data(self, data):
        self._data = data

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, metadata):
        self._metadata = metadata

    def to_hdf(self, hdf=None, group_name="group"):
        """
        Store the Measurement in an HDF5 file

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        if hdf is not None:
            self._hdf5 = hdf
        if group_name is not None:
            self._hdf5.open(group_name)
        self._hdf5["status"] = self.status.string
        if self._import_directory is not None:
            self._hdf5["import_directory"] = self._import_directory
        with self._hdf5.open("input") as hdf_input:
            hdf_input["datatype"] = self.type()
            hdf_input["metadata"] = self.metadata()
            if self._storedata:
                with hdf_input.open("data") as hdf_data:
                    # Store the data as is
                    hdf_data["data"] = self._data

    def from_hdf(self, hdf=None, group_name=None):
        """
        Restore the Measurement from an HDF5 file

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        if hdf is not None:
            self._hdf5 = hdf
        if group_name is not None:
            self._hdf5 = self._hdf5.open(group_name)
        if "import_directory" in self._hdf5.list_nodes():
            self._import_directory = self._hdf5["import_directory"]
        with self._hdf5.open("input") as hdf_input:
            self._type = hdf_input["datatype"]
            self._metadata = hdf_input["metadata"]
            if "data" in hdf_input.list_nodes():
                self._storedata: True
                with hdf_input.open("data") as hdf_data:
                    self._data = hdf_data["data"]

    def save(self):
        """
        Save the object, by writing the content to the HDF5 file and storing an entry in the database.

        Returns:
            (int): Job ID stored in the database
        """
        self.to_hdf()
        job_id = self.project.db.add_item_dict(self.db_entry())
        self._job_id = job_id
        self.status.created = True
        print(
            "The measurement "
            + self.job_name
            + " was saved and received the ID: "
            + str(job_id)
        )
        return job_id

    def reset_job_id(self, job_id):
        pass

    def db_entry(self):
        """
        Generate the initial database entry for the current GenericJob

        Returns:
            (dict): database dictionary {"username", "projectpath", "project", "job", "subjob",
                                         "status", "timestart", "masterid", "parentid"}
        """
        db_dict = {
            "username": s.login_user,
            "projectpath": self.project_hdf5.root_path,
            "project": self.project_hdf5.project_path,
            "job": self.job_name,
            "subjob": self.project_hdf5.h5_path,
            "status": self.status.string,
            "timestart": datetime.now(),
            "masterid": self.master_id,
            "parentid": self.parent_id,
        }
        return db_dict
