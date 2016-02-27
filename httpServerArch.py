# -*- coding: utf-8 -*-  
from SocketServer import ForkingMixIn
from BaseHTTPServer import BaseHTTPRequestHandler
from BaseHTTPServer import HTTPServer
import json
import urllib
import logging



"""
这里多个进程会使用logger对象向同一个文件里面写入
但是如果一次文件写入的数据量小于4096字节应该是一种原子操作，所以这里多个进程应该会安全的写入同一个文件
我们也可以使用sockethandler，使用tcp为我们聚合日志，然后集中向文件写入，这样也就不会出现冲突等问题
"""
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
fd = logging.FileHandler('mysalt.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fd.setFormatter(formatter)
logger.addHandler(fd)

"""
这里ModifiedBaseHTTPRequestHandler继承了BaseHTTPRequestHandler并且做了一点小的修改。
原来的BseHTTPRequestHandler.parse_request()方法没有解析POST方法下的content。
这里我们改写了这个方法，添加了一小段代码。
    self.command == 'post' and self.headers.get('content-length', None) and self.headers.get('content-type', None)
    为真。
    则按照content-length所指定的字节大小从tcp套接字缓冲区内读取相应字节的数据
    并且按照content-type指定的数据格式来解析相应的数据  
"""

class ModifiedBaseHTTPRequestHandler(BaseHTTPRequestHandler):
      global logger
      def log_warning(self, string):
          logger.warning(string) 
      def log_message(self, format, *args):
        """Log an arbitrary message.

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client ip address and current date/time are prefixed to every
        message.

        """
        logger.info('client %s - - %s  %s\n' %(self.client_address[0], format % args, str(self.body)))
        #sys.stderr.write("%s - - [%s] %s\n" %
        #                 (self.client_address[0],
        #                  self.log_date_time_string(),
        #                  format%args))
      def handle_one_request(self):
          self.raw_requestline = self.rfile.readline()
          if not self.raw_requestline:
              self.close_connection = 1
              return
          if not self.parse_request(): # An error code has been sent, just exit
              return
          mname = 'do_' + self.command
          if not hasattr(self, mname):
              self.send_error(501, "Unsupported method (%r)" % self.command)
              return
          method = getattr(self, mname)
          method()
      def parse_request(self):
        """Parse a request (internal).

        The request should be stored in self.raw_requestline; the results
        are in self.command, self.path, self.request_version and
        self.headers.

        Return True for success, False for failure; on failure, an
        error is sent back.

        """
        self.command = None  # set in case of error on the first line
        self.request_version = version = self.default_request_version
        self.close_connection = 1
        requestline = self.raw_requestline
        requestline = requestline.rstrip('\r\n')
        self.requestline = requestline
        words = requestline.split()
        if len(words) == 3:
            command, path, version = words
            if version[:5] != 'HTTP/':
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            except (ValueError, IndexError):
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
                self.close_connection = 0
            if version_number >= (2, 0):
                self.send_error(505,
                          "Invalid HTTP Version (%s)" % base_version_number)
                return False
        elif len(words) == 2:
            command, path = words
            self.close_connection = 1
            if command != 'GET':
                self.send_error(400,
                                "Bad HTTP/0.9 request type (%r)" % command)
                return False
        elif not words:
            return False
        else:
            self.send_error(400, "Bad request syntax (%r)" % requestline)
            return False
        self.command, self.path, self.request_version = command, path, version

        # Examine the headers and look for a Connection directive
        self.headers = self.MessageClass(self.rfile, 0)


        #we add some code here to get the post data if exists
        if self.command.lower() == 'post':
           self.POST = {}
           content_length = int(self.headers.get('content-length', 'None'))
           content_type = self.headers.get('content-type', 'None')
           if content_length and content_type:
              self.body = self.rfile.read(content_length)
              if 'urlencoded' in content_type:
                  self.body = urllib.unquote(self.body)
              elif 'json' is content_type:
                  self.body = json.loads(self.body)
              
              """这里使用POST字典存储http post提交的数据
              """
              for item in self.body.split('&'):
                  _ = item.split('=')
                  self.POST[_[0]] = self.POST[_[1]]



           elif content_length:
               self.body = self.rfile.read()
           else:
               self.body = None
        else:
            if self.command.lower() == 'get':
               """
               使用GET字典存储get方式提交的数据
               """
               self.GET = {}
               self.command = self.command.split('?')[0]
               for item in self.command.split('?')[1].split('&'):
                   _ = item.split('=')
                   self.GET[_[0]] = self.POST[_[1]]

            self.body = None

        
        #content_length = self.headers.get('content-length', 'None')
        #print 'content-lenght: ', content_length
        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif (conntype.lower() == 'keep-alive' and
              self.protocol_version >= "HTTP/1.1"):
            self.close_connection = 0
        return True

        

class ModifiedForkingMixin(ForkingMixIn):
      """ForkingMixIn默认并发数最大为40
      这里ModifiedMixFin继承ForkingMixIn,但是将并发数变为100或者其他自定义数值
      这里暂未使用

      方法搜寻原则：从左到右，广度优先
      """
      max_children = 100

class HttpServerArch(ForkingMixIn, HTTPServer):
      pass



class HttpRequestHandlerArch(ModifiedBaseHTTPRequestHandler):
      pass
