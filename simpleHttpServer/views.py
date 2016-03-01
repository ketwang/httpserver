# -*- coding: utf-8 -*-  
import httpServerArch
def index(request, conn):
  response = httpServerArch.httpResponse(200, 'OK', {'content-length':len('This is a simple test\n'), 'content-type':'text/html'}, 'This is a simple test\n', conn)
  return response

def test(request, conn):
  reason = 'another test!\n'
  response = httpServerArch.httpResponse(200, 'OK', {'content-length':len(reason), 'content-type':'text/html'}, reason, conn)
  return response

def whiteip(request, conn):
  reason = 'white ip !\n'
  response = httpServerArch.httpResponse(404, 'Not Found', {'content-length':len(reason), 'content-type':'text/html'}, reason, conn)
  return response