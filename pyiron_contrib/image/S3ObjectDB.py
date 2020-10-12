import boto3
from botocore.client import Config
#from pyiron_base import PyironObject
import os
import fnmatch
import json

class S3ObjectDB(object):
    def __init__(self, project, config_file = None, config_json = None, group = ''):
        self._project=project.copy()
        # Place to store the object ID from the pyiron database:
        #TODO: implement properly
        self.pyiron_metadata={"ID":"1"}
        self.history=[]
        config = {}
        if config_json is not None:
            config=config_json
        else:
            if config_file is None:
                print('WARN: No config given, trying config.json')
                config_file = './config.json'
            with open(config_file) as json_file:
                config = json.load(json_file)

        s3resource = boto3.resource('s3', 
            config=Config(s3={'addressing_style': 'path'}),
            aws_access_key_id=config['access_key'],
            aws_secret_access_key=config['secret_key'],
            endpoint_url=config['endpoint']
        )
        bucket_name = config['bucket']
        # Now, the bucket object
        self.bucket = s3resource.Bucket(bucket_name)
        self.open(group)

    def print_bucket_info(self): 
        print('Bucket name: {}'.format(self.bucket.name))

    def list_groups(self):
        """
        Return a list of 'directories' ( string followed by / )

        Returns:
            :class:`list`
        """
        groups = []
        group_path_len=len(self.group.split('/'))-1
        for obj in self._list_objects():
            rel_obj_path_spl=obj.key.split('/')[group_path_len:]
            if len(rel_obj_path_spl) > 1:
                groups.append(rel_obj_path_spl[0])
        return groups

    def list_nodes(self):
        """
        Return a list of 'files' ( string not followed by / )

        Returns:
            :class:`list`
        """
        nodes = []
        group_path_len = len(self.group.split('/')) - 1
        for obj in self._list_objects():
            rel_obj_path_spl = obj.key.split('/')[group_path_len:]
            if len(rel_obj_path_spl) == 1:
                nodes.append(rel_obj_path_spl[0])
        return nodes

    def list_all(self):
        return {
            "groups": self.list_groups(),
            "nodes": self.list_nodes(),
        }

    def is_dir(self,path):
        if len(path)>1 and path[-1]!='/':
            path=path+'/'
        for obj in self._list_all_obj_of_bucket():
            if path in obj.key:
                if self.group+path in obj.key:
                    return True
                if path == obj.key[:len(path)]:
                    return True

    def is_file(self,path):
        l=[]
        for obj in self._list_all_obj_of_bucket():
            l.append(obj.key)
        if path in l:
            return True
        if self.group+path in l:
            return True


    def open(self, group):
        if len(group)==0:
            self.group = group
        elif group[-1]== '/':
            self.group = group
        else:
            self.group = group + '/'
        self.history.append(self.group)

    def close(self):
        if len(self.history) > 1:
            del self.history[-1]
        elif len(self.history) == 1:
            self.history[0] = ""
        else:
            print("Err: no history")
        self.group=self.history[-1]

    def upload(self,files,metadata={}):
        """
        Uploads files into the current group of the RDS
        Arguments:
            :class:`list` : List of filenames to upload
        """
        meta={}
        meta.update(self.pyiron_metadata)
        meta.update(metadata)
        for file in files:
            [path,f]=os.path.split(file)
            def printBytes(x):
                print('{} {}/{} bytes'.format(f, x, s))
            s = os.path.getsize(file)
            # Upload file accepts extra_args: Dictionary with predefined keys. One key is Metadata
            self.bucket.upload_file(
                file,
                self.group + f,
                { "Metadata": meta}
            )

    def download(self,files,targetpath="."):
        """
        Download files from current group to local file system (current directory)
        Arguments:
            :class:`list` : List of filenames in the RDS
        """
        if not os.path.exists(targetpath):
            os.mkdir(targetpath)
        for f in files:
            filepath=os.path.join(targetpath,f.split("/")[-1])
            print (filepath)
            self.bucket.download_file(self.group+f,filepath)

    def get_metadata(self,key):
        return self.bucket.Object(self.group + key).metadata

    def get(self,key):
        return self.bucket.Object(self.group + key).get()

    def _list_objects(self):
        l=[]
        for obj in self.bucket.objects.filter(Prefix=self.group):
            l.append(obj)
        return l

    def print_fileinfos(self):
        # prints the filename, last modified date and size for _all_ files in the current group
        for obj in self.bucket.objects.filter(Prefix=self.group):
            print('{} {} {} bytes'.format(obj.key, obj.last_modified, obj.size))

    def _list_all_obj_of_bucket(self):
        l=[]
        for obj in self.bucket.objects.all():
            l.append(obj)
        return l

    def glob(self,path,relpath=False):
        if relpath and  len(self.group) >0:
            path=self.group+'/'+path
        l=[]
        for obj in self.bucket.objects.filter(Prefix=self.group):
            if fnmatch.fnmatchcase(obj.key,path):
                l.append(obj.key)
        return l

    def print_obj_info(self,objlist):
        for obj in objlist:
            print('{} {} {} bytes'.format(obj.key, obj.last_modified, obj.size))


    def remove_group(self,prefix=None,debug=False):
        if prefix==None:
            prefix=self.group
        if debug:
            print('\nDeleting all objects with sample prefix {}/{}.'.format(self.bucket.name, prefix))
        delete_responses = self.bucket.objects.filter(Prefix=prefix).delete()
        if debug:
            for delete_response in delete_responses:
                for deleted in delete_response['Deleted']:
                    print('\t Deleted: {}'.format(deleted['Key']))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self):
        return str(self.list_all())

"""
Some infos about the bucket object:

o.bucket= self.bucket   has the following   options:
--------------------------------------------------------------------------------------------------------------
o.bucket.Acl(                         o.bucket.Website(                     o.bucket.multipart_uploads
o.bucket.Cors(                        o.bucket.copy(                        o.bucket.name
o.bucket.Lifecycle(                   o.bucket.create(                      o.bucket.object_versions
o.bucket.LifecycleConfiguration(      o.bucket.creation_date                o.bucket.objects
o.bucket.Logging(                     o.bucket.delete(                      o.bucket.put_object(
o.bucket.Notification(                o.bucket.delete_objects(              o.bucket.upload_file(
o.bucket.Object(                      o.bucket.download_file(               o.bucket.upload_fileobj(
o.bucket.Policy(                      o.bucket.download_fileobj(            o.bucket.wait_until_exists(
o.bucket.RequestPayment(              o.bucket.get_available_subresources(  o.bucket.wait_until_not_exists(
o.bucket.Tagging(                     o.bucket.load(
o.bucket.Versioning(                  o.bucket.meta

o.bucket.objects   has the following  options:
--------------------------------------------------------------------------------------------------------------
o.bucket.objects.all(        o.bucket.objects.filter(     o.bucket.objects.limit(      o.bucket.objects.pages(
o.bucket.objects.delete(     o.bucket.objects.iterator(   o.bucket.objects.page_size(

o.bucket.Object  is an object of the object store. It is identified by a key, i.e. the full path + file name in the bucket.
Actually, there is no such thing as directories inside the bucket. '/' is a valid character in filenames and we use this fact 
to separate files into directories. 
obj=o.bucket.Object(/path/to/file)  has the following option:
--------------------------------------------------------------------------------------------------------------
obj.Acl(                           obj.download_fileobj(              obj.put(
obj.Bucket(                        obj.e_tag                          obj.reload(
obj.MultipartUpload(               obj.expiration                     obj.replication_status
obj.Version(                       obj.expires                        obj.request_charged
obj.accept_ranges                  obj.get(                           obj.restore
obj.bucket_name                    obj.get_available_subresources(    obj.restore_object(
obj.cache_control                  obj.initiate_multipart_upload(     obj.server_side_encryption
obj.content_disposition            obj.key                            obj.sse_customer_algorithm
obj.content_encoding               obj.last_modified                  obj.sse_customer_key_md5
obj.content_language               obj.load(                          obj.ssekms_key_id
obj.content_length                 obj.meta                           obj.storage_class
obj.content_type                   obj.metadata                       obj.upload_file(
obj.copy(                          obj.missing_meta                   obj.upload_fileobj(
obj.copy_from(                     obj.object_lock_legal_hold_status  obj.version_id
obj.delete(                        obj.object_lock_mode               obj.wait_until_exists(
obj.delete_marker                  obj.object_lock_retain_until_date  obj.wait_until_not_exists(
obj.download_file(                 obj.parts_count                    obj.website_redirect_location

with obj.get() one gets the object.
with obj.download_file('Filename') one downloads the associated file to 'Filename'

getobj=o.bucket.Object(object_key).get() has the following options:
--------------------------------------------------------------------------------------------------------------
getobj.clear(       getobj.fromkeys(    getobj.items(       getobj.pop(         getobj.setdefault(  getobj.values(
getobj.copy(        getobj.get(         getobj.keys(        getobj.popitem(     getobj.update(

"""
