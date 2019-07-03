# -*- coding: utf-8 -*-

import pymysql

class SQL:

    dbc = ("localhost","root","","sim")

    def __init__(self):
        self.db = pymysql.connect(*self.dbc)
        self.cursor = self.db.cursor()

    def query(self,sql,arg):
        self.cursor.execute(sql,arg)
        return self.cursor.fetchone()

    def querymany(self,sql,arg):
        self.cursor.executemany(sql,arg)
        return self.cursor.fetchone()

    def commit(self):
        self.db.commit()

    def close(self):
        self.cursor.close()



