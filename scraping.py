# coding: utf-8
from bs4 import BeautifulSoup
import urllib.request
from datetime import datetime,timezone,timedelta
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import mariadb
import re

connection=mariadb.connect(
        user='myuser',
        password='myuser',
        host='localhost',
        database='tvDB',
        autocommit=False
        )
cursor=connection.cursor()

pattern=re.compile(r'/program/(\d+)')
program_dict = {}

options = Options()
options.set_headless(True)
driver = webdriver.Chrome(chrome_options=options)

endpoint = 'https://tv.yahoo.co.jp'
stlist = [4,10,18,24]
today = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d')
insert_data_params = []

try:
    for st in stlist:
        driver.get('{}/listings/?a=17&d={}&st={:d}'.format(endpoint,today,st))
        res = driver.page_source.encode('utf-8')
        soup = BeautifulSoup(res,'html.parser')
        for content in soup.select('span.detail'):
            try:
                time=content.select_one('span.time')
                if time:
                    program = content.select_one('a.title')
                    href = program['href']
                    with urllib.request.urlopen('{}{}'.format(endpoint,href)) as program_source:
                        program_res = program_source.read().decode('utf-8')
                        program_soup = BeautifulSoup(program_res, 'html.parser')
                        provider = program_soup.find('p',attrs={'itemprop': 'provider'})
                        if provider:
                            matcher=pattern.match(href)
                            program_id=matcher.group(1)
                            if(not(program_id in program_dict)):
                                print('[info]{} {} {} {}'.format(program_id,time.get_text(),program.get_text(),provider.get_text()))
                                insert_data_params.append((program_id,program.get_text(),time.get_text(),provider.get_text()))
                        else:
                            print('[warning]provider is not found at {}'.format(program.get_text()))
            except Exception as e:
                print('[error]'+e)
            sleep(1)

    query = 'insert into tv_program (id,title,time,provider) values(?,?,?,?)'
    cursor.executemany(query,insert_data_params)
    
    connection.commit()
except Exception as e:
    print('[error]'+e)

finally:
    cursor.close()
    connection.close()