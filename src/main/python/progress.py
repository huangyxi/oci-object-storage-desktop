import sys
import os
import configparser
import time
from PySide2.QtCore import Qt, Signal, QThread, QItemSelectionModel
from PySide2.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QDialogButtonBox, QDialog, QProgressBar, QLabel, QSizePolicy

byte_type = {'KB':0, 'MB':1, 'GB':2, 'TB':3, 'PB':4}

class ProgressWindow(QWidget):

    cancel_signal = Signal(int)
    
    def __init__(self, files, filesizes, thread_id):
        super().__init__()
        print(len(files[0]), len(filesizes))
        print(files[0])
        # self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.files_uploaded = 0
        self.files_len = len(files[0])
        self.files = files
        self.filesizes = filesizes
        self.divider = 1024**byte_type[self.filesizes[self.files_uploaded][1][1]]
        self.max = round(self.filesizes[self.files_uploaded][0]/self.divider)
        print(self.max)
        self.setWindowTitle('Uploading Files ({}/{})'.format(self.files_uploaded, len(files[0])))
        self.file_label = QLabel()
        self.file_label.setText("Uploading {}".format(files[0][self.files_uploaded].split('/')[-1]))
        self.size_label = QLabel(" ".join(filesizes[self.files_uploaded][1]))
        self.size_label.setAlignment(Qt.AlignRight)
        print(" ".join(filesizes[self.files_uploaded][1]))
        self.layout = QVBoxLayout()
        self.cancel = QPushButton()
        self.cancel.setText("Cancel")
        self.cancel.clicked.connect(self.cancel_handler)

        self.ok = QPushButton()
        self.ok.setText("OK")
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self.hide)

        self.retry = QPushButton()
        self.retry.setText("Retry")
        self.retry.setEnabled(False)

        self.button_box = QDialogButtonBox()
        self.button_box.setOrientation(Qt.Horizontal)
        self.button_box.addButton(self.ok, QDialogButtonBox.ActionRole)
        self.button_box.addButton(self.cancel, QDialogButtonBox.ActionRole)
        self.button_box.addButton(self.retry, QDialogButtonBox.ActionRole)

        # self.button.clicked.connect(self.test)
        self.progress = QProgressBar(self)
        # self.progress.setGeometry(0, 0, 300, 25)
        self.progress.setMaximum(self.max)
        self.progress.setValue(0)
        self.count = 0

        self.layout.addWidget(self.file_label)
        self.layout.addWidget(self.progress)
        self.layout.addWidget(self.size_label)
        self.layout.addWidget(self.button_box)


        self.retry_label = QLabel()
        self.retry_label.setText("Connection failed")
        self.retry_label.setStyleSheet("QLabel {color: red; }")
        self.layout.addWidget(self.retry_label)
        self.retry_label.setVisible(False)

        self.setLayout(self.layout)

        self.thread_id = thread_id
    
    def test(self):
        self.calc = TestProgress()
        self.calc.countChanged.connect(self.set_progress)
        self.calc.start()

    def next_file(self, *args):
        self.retry_label.setVisible(False)
        self.retry.setEnabled(False)
        if self.files_uploaded < self.files_len:
            self.files_uploaded += 1
            self.setWindowTitle("Uploading Files ({}/{})".format(self.files_uploaded, self.files_len))
            if self.files_uploaded < self.files_len:
                self.count = 0
                self.progress.setValue(0)
                self.file_label.setText("Uploading {}".format(self.files[0][self.files_uploaded].split('/')[-1]))
                self.size_label.setText(" ".join(self.filesizes[self.files_uploaded][1]))
                self.divider = 1024**byte_type[self.filesizes[self.files_uploaded][1][1]]
                self.max = round(self.filesizes[self.files_uploaded][0]/self.divider)
                self.progress.setMaximum(self.max)
                
            else:
                self.file_label.setText("All uploads complete")
                self.size_label.setText("")
                self.progress.setValue(self.max)
                self.ok.setEnabled(True)
                self.cancel.setEnabled(False)
    
    def set_progress(self, count):
        print("{} bytes uploaded".format(count))
        self.count += round(count/self.divider)
        self.progress.setValue(self.count)
    
    def connection_failed(self):
        self.connection_failed_label = QLabel()
        self.connection_failed_label.setText("Connection failed")
    
    def cancel_handler(self):
        self.cancel_signal.emit(self.thread_id)
        self.hide()
    
    def retry_handler(self):
        print("Retry handler")
        # self.retry_label = QLabel()
        # self.retry_label.setText("Connection failed")
        # self.retry_label.setStyleSheet("QLabel {color: red; }")
        # self.layout.addWidget(self.retry_label)
        self.retry_label.setVisible(True)
        self.retry.setEnabled(True)

    


class TestProgress(QThread):

    countChanged = Signal(int)

    def run(self):
        count = 0
        while count < 30:
            count +=2
            time.sleep(1)
            self.countChanged.emit(1)
    
    def __del__(self):
        self.wait()

if __name__ == '__main__':
    app = QApplication([])
    window = ProgressWindow((['test1.txt', 'test2.txt', 'test3.txt'], 'All files'), [(6804103168, ['6.34', 'GB']), (10, ['2', 'KB']), (10, ['3', 'KB'])])
    # time.sleep(10)
    print(window.minimumSizeHint())
    window.resize(192, 146)
    window.show()
    # window.add_progress()
    sys.exit(app.exec_())