from PySide2.QtCore import Qt, Signal, QObject, QTextCodec, QThread
from PySide2.QtGui import QColor, QCursor
from PySide2.QtWidgets import QWidget, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QTreeWidget, QTreeWidgetItem, QDialogButtonBox, QDialog, QLineEdit, QAbstractItemView, QMenuBar, QMenu, QAction, QProgressBar
from oci_manager import oci_manager, UploadId
from config import ConfigWindow
from progress import ProgressWindow
from util import get_filesize
import sys
import os

class UploadThread(QThread):

    file_uploaded = Signal(str, str)
    bytes_uploaded = Signal(int)
    all_files_uploaded = Signal(int)
    upload_failed = Signal()

    def __init__(self, files, bucket_name, oci_manager, filesizes, thread_id):
        """
        UploadThread allows upload jobs to run in a differen;t thread than the application, so the application doesn't stall or freeze
        
        :param files: A tuple of files. First element is a list of absolute paths to the files. Second element is the mimetype of files
        :type files: tuple
        :param bucket_name: The name of the bucket for uploading into
        :type bucket_name: string
        :param oci_manager: The OCI manager to use for OCI related tasks
        :type: :class: 'oci_manager.oci_manager'
        """
        super().__init__()
        self.files = files
        self.bucket_name = bucket_name
        self.os_client = oci_manager.get_os()
        self.namespace = oci_manager.get_namespace()
        self.upload_manager = oci_manager.get_upload_manager()
        self.upload_id_manager = UploadId()
        self.upload_id = None
        self.upload_id_manager.test.connect(self.log_id)
        self.filesizes = filesizes
        self.threadactive = True
        self.setTerminationEnabled()
        self.thread_id = thread_id

        self.current_upload = None

    def log_id(self, id):
        """
        Slot that prints the upload id when a new upload is created

        :param id: Upload ID of upload
        :type id: string
        """
        print("Upload ID: {}".format(id))
        self.upload_id = id
    
    def retry(self):
        try:
            self.upload_manager.resume_upload_file(self.namespace, self.bucket_name, self.current_upload["object_name"],\
                    self.current_upload["file_path"], self.upload_id, progress_callback=self.progress_callback, mixin=self.upload_id_manager, part_size=10485760)
        except:
            print("Retry connection failed")
            self.connection_failed()
        else:
            self.file_uploaded.emit(self.current_upload["object_name"], self.current_upload["filesize"])
    
    def connection_failed(self):
        print("Connection failed")
        self.upload_failed.emit()
    
    def connection_canceled(self):
        print("Connection cancelled")
        self.quit()
    
    def progress_callback(self, bits):
        """
        Callback function for the uploading

        :param bits: The amount of bits uploaded
        :type bits: int
        """
        self.bytes_uploaded.emit(bits)
        
    def __del__(self):
        self.wait()

    def stop(self):
        print("Connection stopped")
        self.threadactive = False
        self.upload_manager.abort(self.upload_id)
        self.wait()
    
    def upload_file(self, file, object_name):
        """
        Upload the file and pass in a callback function

        :param file: The absolute path of the file
        :type file: string
        """
        try:
            response = self.upload_manager.upload_file(self.namespace, self.bucket_name, object_name, file, progress_callback=self.progress_callback, mixin=self.upload_id_manager, part_size=10485760)
        except:
            self.connection_failed()
        else:
            print(response)
            return response
    
    def run(self):
        """

        """
        for i, file in enumerate(self.files[0]):
            if os.path.isfile(file) and self.threadactive:
                self.current_upload = {"object_name":file.split('/')[-1], "file_path":file, "filesize": " ".join(self.filesizes[i][1])}
                response = self.upload_file(file, file.split('/')[-1])
                if response:
                    self.file_uploaded.emit(file.split('/')[-1], " ".join(self.filesizes[i][1]))
            elif os.path.isdir(file) and self.threadactive:
                split_dir = file.split('/')
                dir_length = len(file) - len(split_dir[-2]) - 1
                root_dir = True
                for dir, _, filenames in os.walk(file):
                    for filename in filenames:
                        subfile = "{}/{}".format(dir, filename) if not root_dir else "{}{}".format(dir, filename)
                        print(subfile[dir_length:])
                        self.current_upload = {"object_name":subfile[dir_length:], "file_path":subfile, "filesize": " ".join(self.filesizes[i][1])}
                        response = self.upload_file(subfile, subfile[dir_length:])
                        if response:
                            self.file_uploaded.emit(file.split('/')[-1], " ".join(self.filesizes[i][1]))
                    root_dir = False
        self.all_files_uploaded.emit(self.thread_id)