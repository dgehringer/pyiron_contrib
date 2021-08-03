import fnmatch
import io
import json
import os
import posixpath
from functools import lru_cache

import boto3
from botocore.client import Config

from pyiron_base.generic.filedata import load_file, FileDataTemplate


class S3FileData(FileDataTemplate):
    """FileData stores an instance of a data file from an S3 system, e.g. a single Image from a measurement."""
    def __init__(self, s3obj, filename=None, filetype=None):
        """FileData class to store data and associated metadata.

            Args:
                s3obj (s3object): s3object containing a file with data
                filename (str): filename associated with the data.
                filetype (str): File extension associated with the type data,
                                If provided this overwrites the assumption based on the extension of the filename.
        """
        self._s3obj = s3obj
        if filename is None:
            self.filename = s3obj.key.split('/')[-1]
        else:
            self.filename = filename
        if filetype is None:
            filetype = os.path.splitext(self.filename)[1]
            if filetype == '' or filetype == '.':
                self.filetype = None
            else:
                self.filetype = filetype[1:]
        else:
            self.filetype = filetype
        self._data = None
        self._metadata = self._s3obj.metadata

    @property
    @lru_cache()
    def data(self):
        """Return the associated data."""
        if self._data is None:
            self._s3obj = self._s3obj.get()
            self._data = self._s3obj["Body"].read()
        return load_file(io.BytesIO(self._data), filetype=self.filetype)

    @property
    def metadata(self):
        return self._metadata

    def __repr__(self):
        return f"FileData containing {self.filename}."

    def _ipython_display_(self):
        result = f"File    {self.filename}   with meta data:\n"
        result += "-------------------------------------------\n"
        for key, value in self.metadata.items():
            result += f"{key}:  {value}\n"
        print(result)


class S3ioConnect:
    def __init__(self, credentials=None, bucket_name=None):
        """Establishes connection to a specific 'bucket' of a S3 type object store.

            Args:
                credentials (str/dict/boto3.resource/None):
                        if str: path to a json configuration file with login credentials for the bucket.
                        if dict: dictionary containing the login credentials.
                        if boto3.resource: This resource is used as is, requires bucket_name to be specified.
                        if None: use Credentials as obtained by boto3, requires bucket_name to be specified.
                bucket_name(str/None): Name of the bucket, overwrites name given in the config.

            The configuration needs to provide the following information:
                access_key or aws_access_key_id (str)
                secret_key or aws_secret_access_key (str)
            And may contain these additional fields:
                endpoint or endpoint_url (str)
                bucket (str)
            Each additional keyword is passed on to boto3 as is.
        """
        if (isinstance(credentials, boto3.resources.base.ServiceResource)):
            if bucket_name is None:
                raise ValueError("Only boto3.resource given. The bucket_name needs to be specified!")
            self.s3resource = credentials
            self.bucket_name = bucket_name
        # boto3 looks for the (missing) credentials at  ~/.aws/credentials or at environment variables:
        # AWS_ACCESS_KEY_ID  AWS_SECRET_ACCESS_KEY  etc.
        elif credentials is None:
            if bucket_name is None:
                raise ValueError("The bucket_name needs to be specified!")
            self.s3resource = boto3.resource('s3')
        else:
            if isinstance(credentials, str):
                with open(credentials) as json_file:
                    credentials = json.load(json_file)
            if not isinstance(credentials, dict):
                raise TypeError("credentials is not one of the supported types but {}.".format(type(credentials)))
            credentials = credentials.copy()
            config = credentials.pop('config', Config(s3={'addressing_style': 'path'}))
            key = credentials.pop('access_key', None) or credentials.pop('aws_access_key_id', None)
            if key is not None:
                credentials['aws_access_key_id'] = key
            key = credentials.pop('secret_key', None) or credentials.pop('aws_secret_access_key', None)
            if key is not None:
                credentials['aws_secret_access_key'] = key
            key = credentials.pop('endpoint', None) or credentials.pop('endpoint_url', None)
            if key is not None:
                credentials['endpoint_url'] = key
            self.bucket_name = credentials.pop("bucket", None)
            if bucket_name is not None:
                self.bucket_name = bucket_name
            if self.bucket_name is None:
                raise ValueError("Bucket name needs to be provided.")

            self.s3resource = boto3.resource('s3',
                                             config=config,
                                             **credentials
                                             )

        self.bucket = self.s3resource.Bucket(self.bucket_name)

    @property
    def endpoint_url(self):
        return self.s3resource.meta.client.meta.endpoint_url


class FileS3IO:
    def __init__(self, config=None, path='/', *, bucket_name=None):
        """
            Establishes connection to a specific 'bucket' of a S3 type object store.

            Args:
                config (str/dict/:class:`S3IO_connect`/boto3.ressource/None):
                    Provides access information for the S3 type object store:
                        str: path to a json configuration file with login credentials for the bucket.
                        dict: dictionary containing the login credentials.
                        S3IO_connect: Instantiated S3IO_connect class to access the S3 system.
                        boto3.resource: Instantiated boto3.resource, requires bucket_name to be given.
                        None: Use default credentials from boto3, requires bucket_name to be given.
                path (str): Initial group in the bucket which is opened.
                bucket_name(str/None): Name of the bucket if not included/different from the config.

            The configuration needs to provide the following information:
                {
                access_key : ""
                secret_key : ""
                endpoint : ""
                bucket : ""
                }
        """
        self.history = [path]
        if isinstance(config, S3ioConnect):
            self._s3io = config
        else:
            self._s3io = S3ioConnect(credentials=config, bucket_name=bucket_name)

        self._bucket = self._s3io.bucket
        self._s3_path = None
        self.s3_path = path

    @property
    def s3_path(self):
        """
        Get the path in the S3 object store starting from the root group - meaning this path starts with '/'

        Returns:
            str: S3 path
        """
        return self._s3_path

    @s3_path.setter
    def s3_path(self, path):
        """
        Set the path in the S3 object store starting from the root group

        Args:
            path (str): S3 path
        """
        if (path is None) or (path == ""):
            path = "/"
        self._s3_path = posixpath.normpath(path)
        if not posixpath.isabs(self._s3_path):
            self._s3_path = "/" + self._s3_path
        if not self._s3_path[-1] == '/':
            self._s3_path = self._s3_path + '/'

    @property
    def _bucket_path(self):
        """
        The bucket object internally does not use a '/' to indicate the root group.

        Return:
            str: Internal path in the bucket.
        """
        return self._s3_path[1:]

    @property
    def bucket_info(self):
        return {'bucket_name': self._bucket.name,
                'endpoint_url': self._s3io.endpoint_url}

    def list_groups(self):
        """
        List directories/groups in the current group.

        Returns:
            list: list of directory names.
        """
        groups = []
        group_path_len = len(self._bucket_path.split('/')) - 1
        for obj in self._list_objects():
            rel_obj_path_spl = obj.key.split('/')[group_path_len:]
            if len(rel_obj_path_spl) > 1:
                if rel_obj_path_spl[0] not in groups:
                    groups.append(rel_obj_path_spl[0])
        return groups

    def list_nodes(self):
        """
        List of 'files' ( string not followed by '/' ) in the current group.

        Returns:
            list: list of file names.
        """
        nodes = []
        for obj in self._bucket.objects.filter(Prefix=self._bucket_path, Delimiter='/'):
            nodes.append(obj.key.split('/')[-1])
        return nodes

    def list_all(self):
        """
        Combination of list_groups() and list_nodes() in one dictionary with the corresponding keys:
        - 'groups': Sub-folder/ -groups.
        - 'nodes': Files in the current group.

        Returns:
            dict: dictionary with all items in the group.
        """
        return {
            "groups": self.list_groups(),
            "nodes": self.list_nodes(),
        }

    def _to_abs_bucketpath(self, path):
        """Helper function to convert a given path to an absolute path inside the S3 bucket."""
        if path is None or "":
            path = self._bucket_path
        if posixpath.isabs(path):
            path = path[1:]
        else:
            path = self._bucket_path + path
        return path

    def is_dir(self, path):
        """
        Check if given path is a directory.

        Args:
            path (str): path to check.

        Returns:
            bool: True if path is a directory.
        """
        path = self._to_abs_bucketpath(path)
        if len(path) > 1 and path[-1] != '/':
            path = path + '/'
        objs = list(self._bucket.objects.filter(Prefix=path))
        return len(objs) > 0

    def is_file(self, path):
        """
        Check if given path is a file.

        Args:
            path (str): path to check.

        Returns:
            bool: True if path is a file.
        """
        path = self._to_abs_bucketpath(path)
        objs = list(self._bucket.objects.filter(Prefix=path))
        for obj in objs:
            if obj.key == path:
                return True
        return False

    def open(self, group):
        """
        Opens the provided group (create group if not yet present).

        Args:
            group (str): group to open/create.
        """
        new = self.copy()
        new.s3_path = self.s3_path + group
        new.history.append(new.s3_path)
        return new

    def copy(self):
        """
        Copy the Python object which links to the S3 object store.

        Returns:
            FileS3IO: New FileS3io object pointing to the same S3 object store
        """
        new = FileS3IO(config=self._s3io, path=self.s3_path)
        return new

    def close(self):
        """   Close current group and open previous group.         """
        if len(self.history) > 1:
            del self.history[-1]
        elif len(self.history) == 1:
            self.history[0] = "/"
        else:
            print("Err: no history")
        self._s3_path = self.history[-1]

    def upload(self, files, metadata=None):
        """
        Uploads files into the current group of the S3 object store.

        Arguments:
            files (list/str) : List of filenames/ filename to upload
            metadata (dictionary): metadata of the files (Not nested, only "str" type)
        """
        if metadata is None:
            metadata = {}

        if isinstance(files, str):
            files = [files]

        for file in files:
            [_, filename] = os.path.split(file)

            self._bucket.upload_file(
                file,
                self._bucket_path + filename,
                {"Metadata": metadata}
            )

    def download(self, files, targetpath="."):
        """
        Download files from current group to local file system (current directory is default)

        Arguments:
            files (list/str): List of filenames in the S3 object store.
            targetpath (str): Path in the local data system, to which the files should be downloaded.
        """
        if not os.path.exists(targetpath):
            os.mkdir(targetpath)
        if isinstance(files, str):
            files = [files]

        for f in files:
            filepath = os.path.join(targetpath, f.split("/")[-1])
            print(filepath)
            self._bucket.download_file(self._bucket_path + f, filepath)

    def get_metadata(self, file):
        """
        Returns the metadata of a file.

        Args:
            file (str): path to a file of the bucket.
        Returns:
             dict: metadata field associated with the file.
        """
        file = self._to_abs_bucketpath(file)
        return self._bucket.Object(file).metadata

    def _s3io_object(self, file):
        """
        Returns an object with access to the S3 object store which can be downloaded via .get()

        Args:
            file (str): path to a file of the bucket.
        Returns:
        """
        file = self._to_abs_bucketpath(file)
        s3object = S3FileData(s3obj=self._bucket.Object(file))
        return s3object

    def get(self, file):
        """
        Returns a s3.Object containing the requested file.

        Args:
            file(str): a path like string.
        Returns:
             Object containing a file.
        """
        file = self._to_abs_bucketpath(file)
        return self._bucket.Object(file).get()

    def put(self, data_obj, path=None, metadata=None):
        """
            Upload a data_obj to the current group/ the provided path.

            Args:
                data_obj(:class:`pyiron_base.generic.filedata.FileData`): data object to upload the data from.
                path(str/None):
                metadata(dict/None): metadata to be used (has to be a dictionary of type {"string": "string, }).
                      Provided metadata overwrites the one possibly present in the data object.
        """
        if self.is_dir(path):
            path = self._to_abs_bucketpath(path)
        else:
            raise ValueError("No valid path specified!")
        if path[-1] != '/':
            path = path + '/'
        path = path + data_obj.filename

        data = data_obj.data()
        if metadata is None:
            metadata = data_obj.metadata
        if metadata is None:
            metadata = {}
        if not isinstance(path, str):
            raise ValueError
        if data is None:
            raise ValueError
        self._bucket.put_object(Key=path, Body=data, Metadata=metadata)

    def _list_objects(self):
        return self._bucket.objects.filter(Prefix=self._bucket_path)

    def print_fileinfos(self):
        """
            Prints the filename, last modified date and size for all files in the current group,
            recursively including sub groups.
        """
        for obj in self._bucket.objects.filter(Prefix=self._bucket_path):
            print('/{} {} {} bytes'.format(obj.key, obj.last_modified, obj.size))

    def _list_all_files_of_bucket(self):
        return list(self._bucket.objects.all())

    def glob(self, path):
        """
            Return a list of paths matching a pathname pattern.
            The pattern may contain simple shell-style wildcards a la fnmatch.

            Args:
                path(str): a path like string which may contain shell-style wildcards.

            Return:
                list: List of file names (str) matching the provided path pattern.
        """
        path = self._to_abs_bucketpath(path)
        l = []
        for obj in self._bucket.objects.filter(Prefix=self._bucket_path):
            if fnmatch.fnmatchcase(obj.key, path):
                l.append(obj.key)
        return l

    @staticmethod
    def print_file_info(filelist):
        """
            Prints filename, last_modified, and size of each file in the provided list of file objects.

            Args:
                filelist (list): List containing objects from a bucket.
        """
        for obj in filelist:
            print('/{} {} {} bytes'.format(obj.key, obj.last_modified, obj.size))

    def remove_file(self, file):
        """
            Deletes the object associated with a file.

            Args:
                file (str/None): path like string to the file to be removed.
        """
        if not self.is_file(file):
            raise ValueError("{} is not a file.".format(file))
        file = self._to_abs_bucketpath(file)
        self._bucket.Object(file).delete()
        #self._remove_object(prefix=file, debug=debug)

    def remove_group(self, path=None, debug=False):
        """
            Deletes the current group with all it's content recursively.

            Args:
                path (str/None): group to be removed recursively.
                debug(bool): If True, additional information is printed.
        """
        if path is None:
            path = self._s3_path
        if not self.is_dir(path):
            raise ValueError("{} is not a group.".format(path))
        path = self._to_abs_bucketpath(path)
        self._remove_object(prefix=path, debug=debug)

    def _remove_object(self, prefix, debug=False):
        """
            Deletes all objects matching the provided prefix.

            Args:
                prefix(str): All objects with this prefix will be removed.
                debug(bool): If True, additional information is printed.
        """
        if debug:
            print('\nDeleting all objects with sample prefix {}/{}.'.format(self._bucket.name, prefix))
        delete_responses = self._bucket.objects.filter(Prefix=prefix).delete()
        if debug:
            for delete_response in delete_responses:
                for deleted in delete_response['Deleted']:
                    print('\t Deleted: {}'.format(deleted['Key']))

    def __enter__(self):
        """ Compatibility function for the with statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Compatibility function for the with statement."""
        self.close()

    def __repr__(self):
        """
        Human readable string representation.

        Return:
            str: list all nodes and groups as string.
        """
        return str(self.list_all())

    def __getitem__(self, item):
        """
        Get/ read (meta) data from the S3 object store

        Args:
            item (str, slice): path to the data or key of the data object

        Returns:
            dict/s3.Object:  meta data or data object
        """
        if isinstance(item, slice):
            raise NotImplementedError("Implement if needed, e.g. for [:]")
        else:
            item_lst = item.split("/")
            if len(item_lst) == 1 and item_lst[0] != "..":
                if item == "":
                    return self
                if item in self.list_nodes():
                    return self._s3io_object(item)
                if item in self.list_groups():
                    return self.open(item)
                raise ValueError("Unknown item: {}".format(item))
            else:
                item_abs_lst = (
                    os.path.normpath(os.path.join(self.s3_path, item))
                        .replace("\\", "/")
                        .split("/")
                )
                s3_object = self.copy()
                s3_object.s3_path = "/".join(item_abs_lst[:-1])
                return s3_object[item_abs_lst[-1]]

