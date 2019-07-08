#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
import requests
import os
from PyPDF2 import PdfFileReader
from whoosh import index
from whoosh.index import create_in
from whoosh.fields import Schema, TEXT, ID
import sys
from whoosh.qparser import QueryParser
from whoosh import scoring
from whoosh.index import open_dir

#abstract class (do not instantiate)
class Searchable:
    
    #provides a full text search of all pdfs over the root
    def fullTextSearch(self, terms):
        
        self.createSearchableData(self.root)
        
        self.phrases = terms
        results = []
    
        for i in range(len(self.phrases)):
            results.append(self.termQuery(self.phrases[i]))
        
        return results
    
    
    #helper, creates a searchable index
    def createSearchableData(self, root):   
        schema = Schema(title=TEXT(stored=True),path=ID(stored=True), content=TEXT)
        if not os.path.exists("indexdir"):
            os.mkdir("indexdir")

        ix = index.create_in("indexdir", schema)
        writer = ix.writer()

        filepaths = [os.path.join(root,i) for i in os.listdir(root)]
        for path in filepaths:
            text = self.getPDFText(path)
            writer.add_document(title=path.split("\\")[1], path=path,                content=text)
        writer.commit()
    
    #helper, searches index for particular phrase and prints results
    def termQuery(self, phrase):

        ix = open_dir("indexdir")
 
        qp = QueryParser("content", schema=ix.schema)
        q = qp.parse(phrase)
    
        res = []
    
        with ix.searcher() as s:
            results = s.search(q, limit=None)
            for result in results:
                res.append(str(result))
            return res
        
    #returns text found in pdf
    def getPDFText(self, path):
        text = ''

        with open(path, 'rb') as f:
            pdf = PdfFileReader(f)
            numPages = pdf.getNumPages()
            for pageNum in range(numPages):
                page = pdf.getPage(pageNum)
                
                #reads in specific page of doc
                try:
                    text += page.extractText().replace('\n', ' ')
                except TypeError:
                    text += self.readImage(path, pageNum)

        return text
    
    def readImage(self, path, pageNum):
        

#searches through pma database; can call fullTextSearch and deleteFiles
class PMASearch(Searchable):
    
    def __init__(self, s, e, c, r):
        super().__init__
        self.start = s         #start date of search (inclusive)
        self.end = e           #end date of search (inclusive)
        self.committee = c     #advisory committee (use 'all' to search all committees)
        self.root = r          #folder that you would like to save summaries to
        
        for i in range(self.start.monthsInBetween(self.end)):
            self.getSummaries(self.getPMAS(self.start.getDate(), self.start.lastDay()))
            self.start.nextMonth()
        
        self.getSummaries(self.getPMAS(self.end.firstDay(), self.end.getDate()))
        
    #deletes all files that were downloaded (use after performing full text searches)    
    def deleteFiles(self):
        filepaths = [os.path.join(self.root,i) for i in os.listdir(self.root)]
        for path in filepaths:
            os.remove(path)
        
    #helper, returns url of pma summary pdf and determines if pma has summary
    def getSummary(self, URL):

        page_response = requests.get(URL, timeout=5)
        page_content = BeautifulSoup(page_response.content, "html.parser")

        textContent = page_content.find_all(style="text-decoration:underline;")

        #checks if original pma contains a summary
        for element in textContent:
            if(element.text == 'Summary of Safety and Effectiveness'):
                return 'http://www.accessdata.fda.gov/cdrh_docs/pdf' + URL[69:71] + '/' + URL[68:75] + 'B.pdf'

        return URL[68:75] + ' does not contain a Summary of Safety and Effectiveness' 

    #helper, gets the url of pmas given a range of time
    def getPMAS(self, fromDate, toDate):

        options = Options()
        options.headless = True

        driver = webdriver.Firefox(options = options)
        driver.get('https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm')

        fromBox = driver.find_element_by_name('decisiondatefrom')
        toBox = driver.find_element_by_name('decisiondateto')
        searchBox = driver.find_element_by_name('Search')
        advisoryBox = driver.find_element_by_name('advisorycommittee')

        fromBox.send_keys(fromDate)
        toBox.send_keys(toDate)

        advisorySelect = Select(advisoryBox)

        if(self.committee == 'all'):
            advisorySelect.select_by_index(0)
        else:
            advisorySelect.select_by_value(self.committee)


        searchBox.click()

        rppBox = ''

        try:
            rppBox = driver.find_element_by_name('rpp')
        except:
            url = driver.current_url
            driver.quit()
            return url

        select = Select(rppBox)
        select.select_by_value('500')

        url = driver.current_url

        driver.quit()

        return url

    #helper, downloads all pma summary pdfs in the url
    def getSummaries(self, url):

        startUrl = 'https://www.accessdata.fda.gov'

        page_response = requests.get(url, timeout=5)
        page_content = BeautifulSoup(page_response.content, "html.parser")

        textContent = page_content.find_all(style="text-decoration:underline;")

        #looks through all pmas in url
        for element in textContent:
            string = str(element)
            deviceURL = startUrl + string[9: 9 + string[9:len(string)].index('\"')]

            #if the pma is original
            if len(deviceURL) == 75:

                file_url = self.getSummary(deviceURL)

                #if the pma does not have a summary
                if(len(file_url) == 62):
                    print(file_url)
                else:
                    r = requests.get(file_url, stream = True) 

                    #download pmas into Summaries folder
                    with open(self.root + '/' + file_url[47:59],"wb") as pdf: 
                        for chunk in r.iter_content(chunk_size=1024): 
                            if chunk: 
                                pdf.write(chunk)

#creates an object to be searched from already existing pdfs; can call fullTextSearch                                
class RootSearch(Searchable):
    
    def __init__(self, r):
        self.root = r
                                
#date helper class
class Date:
    
    daysInMonth = [[0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]]
    
    
    def __init__(self, month, day, year):
        self.m = month
        self.d = day
        self.y = year
    
    def getDate(self):
        
        if(len(str(self.m)) > 1):
            toReturn = str(self.m)
        else:
            toReturn = '0' + str(self.m)
            
        if(len(str(self.d)) > 1):
            toReturn += '/' + str(self.d)
        else:
            toReturn += '/0' + str(self.d)
            
        toReturn += '/' + str(self.y)
        
        return toReturn
    def nextMonth(self):
        if(self.m == 12):
            self.m = 1
            self.y += 1
        else:
            self.m +=1
        self.d = 1
            
    def prevMonth(self):
        if(self.m == 1):
            self.m = 12
            self.y -= 1
        else:
            self.m -= 1
        self.d = 1
    
    def lastDay(self):
        return str(self.m) + '/' + str(self.daysInMonth[self.y%4][self.m]) + '/' + str(self.y)
    
    def firstDay(self):
        return str(self.m) + '/' + '01' + '/' + str(self.y)
    
    def monthsInBetween(self, other):
        return (other.y - self.y)*12 + (other.m - self.m)
    
#search = PMASearch(Date(4,1,2018), Date(7,1,2018), 'all', 'Summaries')
search = RootSearch('Summaries')
out = search.fullTextSearch(['indications', 'finite element'])

for i in range(len(out)):
        print(search.phrases[i] + ':')
        
        for element in out[i]:
            print(element)

