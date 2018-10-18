"""
Purpose: To scrape information from the second hand songs web site about
cliques of songs
"""
import requests
import json
import urllib
from HTMLParser import HTMLParser
import numpy as np
import pickle
import os

LIST_NEW_URL = "https://secondhandsongs.com/explore"
PERFORMANCE_URL = "https://secondhandsongs.com/performance/"

def resolve(search):
    url = 'https://secondhandsongs.com/search/object?caption=%s' % (search)
    r = requests.get(url)
    return r.json()

def readPage(URL):
    try:
        connection = urllib.urlopen(URL)
        encoding = connection.headers.getparam('charset')
        if encoding:
            page = connection.read().decode(encoding)
            connection.close()
            return page
        else:
            return connection.read()
    except(Exception):
        print("Failed to connect to url")
        return ""
    return ""

def getAttrDict(attrs):
    attrDict = {}
    for attr in attrs:
        if attr[1]:
            attrDict[attr[0]] = attr[1].strip()
        else:
            attrDict[attr[0]] = ""
    return attrDict

class ListPageParser(HTMLParser):
    """
    Class for getting all of the links on a page that lists songs
    """
    (START, WAITING_FOR_TBODY, WAITING_FOR_ROW, WAITING_FOR_LINK, END) = (0, 1, 2, 3, 4)

    def __init__(self):
        HTMLParser.__init__(self)
        self.state = ListPageParser.START
        self.IDs = []
    
    def handle_starttag(self, tag, attrs):
        if tag == "table" and self.state == ListPageParser.START:
            self.state = ListPageParser.WAITING_FOR_TBODY
        elif tag == "tbody" and self.state == ListPageParser.WAITING_FOR_TBODY:
            self.state = ListPageParser.WAITING_FOR_ROW
        elif tag == "tr" and self.state == ListPageParser.WAITING_FOR_ROW:
            self.state = ListPageParser.WAITING_FOR_LINK
        elif tag == "a" and self.state == ListPageParser.WAITING_FOR_LINK and len(attrs) > 0:
            attrDict = getAttrDict(attrs)
            if "href" in attrDict:
                fields = attrDict["href"].split("/")
                for i in range(len(fields) - 1):
                    if fields[i] == "performance":
                        self.IDs.append(int(fields[i+1]))
                        break
            self.state = ListPageParser.WAITING_FOR_ROW

    def handle_endtag(self, tag):
        if tag == "table" and self.state == ListPageParser.WAITING_FOR_ROW:
            self.state = ListPageParser.END

    def handle_data(self, data):
        return


class PerformanceParser(HTMLParser):
    """
    Class for getting all performances in a clique of covers
    """
    (START, WAITING_FOR_TBODY, WAITING_FOR_ROW, WAITING_FOR_FIELD, CHECKING_YOUTUBE, CHECKING_TITLE, GETTING_TITLE, CHECKING_PERFORMER, GETTING_PERFORMER, GETTING_DATE, GETTING_INFO, END) = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    
    def __init__(self):
        HTMLParser.__init__(self)
        self.state = PerformanceParser.START
        self.className = ""
        self.song = {}
        self.songs = []
    
    def handle_starttag(self, tag, attrs):
        if tag == "table" and self.state == PerformanceParser.START and len(attrs) > 0:
            attrDict = getAttrDict(attrs)
            if "id" in attrDict:
                if attrDict["id"].find("versions") > -1:
                    self.state = PerformanceParser.WAITING_FOR_TBODY
        elif tag == "tbody" and self.state == PerformanceParser.WAITING_FOR_TBODY:
            self.state = PerformanceParser.WAITING_FOR_ROW
        elif tag == "tr" and self.state == PerformanceParser.WAITING_FOR_ROW:
            self.state = PerformanceParser.WAITING_FOR_FIELD
            self.song = {"youtube":False}
        elif tag == "td" and self.state == PerformanceParser.WAITING_FOR_FIELD and len(attrs) > 0:
            attrDict = getAttrDict(attrs)
            if "class" in attrDict:
                c = attrDict["class"]
                if c == "field-icon":
                    self.state = PerformanceParser.CHECKING_YOUTUBE
                elif c == "field-title":
                    self.state = PerformanceParser.CHECKING_TITLE
                elif c == "field-performer":
                    self.state = PerformanceParser.CHECKING_PERFORMER
                elif c == "field-date":
                    self.state = PerformanceParser.GETTING_DATE
                elif c == "field-info":
                    self.state = PerformanceParser.GETTING_INFO
                else:
                    print("Unrecognized field: ", c)
        elif tag == "i" and self.state == PerformanceParser.CHECKING_YOUTUBE:
            self.song["youtube"] = True
            self.state = PerformanceParser.WAITING_FOR_FIELD
        elif tag == "a" and len(attrs) > 0:
            attrDict = getAttrDict(attrs)
            if self.state == PerformanceParser.CHECKING_TITLE:
                fields = attrDict["href"].split("/")
                for i in range(len(fields) - 1):
                    if fields[i] == "performance":
                        self.song["ID"] = int(fields[i+1])
                        break
            elif self.state == PerformanceParser.CHECKING_PERFORMER:
                fields = attrDict["href"].split("/")
                for i in range(len(fields) - 1):
                    if fields[i] == "artist":
                        self.song["artistID"] = int(fields[i+1])
                        break
        elif tag == "span":
            if self.state == PerformanceParser.CHECKING_TITLE:
                self.state = PerformanceParser.GETTING_TITLE
            elif self.state == PerformanceParser.CHECKING_PERFORMER:
                self.state = PerformanceParser.GETTING_PERFORMER
                
    def handle_endtag(self, tag):
        if tag == "tr" and self.state == PerformanceParser.WAITING_FOR_FIELD:
            self.songs.append(self.song)
            self.state = PerformanceParser.WAITING_FOR_ROW
        elif tag == "td" and self.state == PerformanceParser.CHECKING_YOUTUBE:
            self.state = PerformanceParser.WAITING_FOR_FIELD
        elif tag == "table" and not self.state == PerformanceParser.START:
            self.state = PerformanceParser.END
    
    def handle_data(self, data):
        if self.state == PerformanceParser.END:
            return
        if self.state == PerformanceParser.GETTING_TITLE:
            self.song["title"] = data
            self.state = PerformanceParser.WAITING_FOR_FIELD
        elif self.state == PerformanceParser.GETTING_PERFORMER:
            self.song["artist"] = data
            self.state = PerformanceParser.WAITING_FOR_FIELD
        elif self.state == PerformanceParser.GETTING_DATE:
            self.song["date"] = data
            self.state = PerformanceParser.WAITING_FOR_FIELD
        elif self.state == PerformanceParser.GETTING_INFO:
            self.song["info"] = data.rstrip()
            self.state = PerformanceParser.WAITING_FOR_FIELD


class YoutubeVideoParser(HTMLParser):
    """
    A class for finding the youtube uri
    """
    (START, WAITING_YOUTUBE, END) = (0, 1, 2)
    def __init__(self):
        HTMLParser.__init__(self)
        self.uri = None
        self.state = YoutubeVideoParser.START
    
    def handle_starttag(self, tag, attrs):
        if self.state == YoutubeVideoParser.START and tag == "div" and len(attrs) > 0:
            attrDict = getAttrDict(attrs)
            if "id" in attrDict:
                if attrDict["id"].find("perf_youtube") > -1:
                    self.state = YoutubeVideoParser.WAITING_YOUTUBE
        elif self.state == YoutubeVideoParser.WAITING_YOUTUBE and tag == "iframe" and len(attrs) > 0:
            attrDict = getAttrDict(attrs)
            if "src" in attrDict:
                src = attrDict["src"]
                if src.find("youtube.com/embed") > -1:
                    src = src.split("/embed/")[1]
                    src = src.split("?")[0]
                    self.uri = src
                    self.state = YoutubeVideoParser.END
    

class OopsChecker(HTMLParser):
    """
    Class for checking to see if the page exists
    """
    (START, CHECKING, END) = (0, 1, 2)
    def __init__(self):
        HTMLParser.__init__(self)
        self.oops = False
        self.state = OopsChecker.START
    
    def handle_starttag(self, tag, attrs):
        if tag == "h1" and self.state == OopsChecker.START:
            self.state = OopsChecker.CHECKING
    
    def handle_data(self, data):
        if self.state == OopsChecker.CHECKING:
            if data.find("Oops") > -1:
                self.oops = True
                self.state = OopsChecker.END

def printDebugOut(s, fout):
    print(s)
    fout.write(s+"\n")
    fout.flush()

def getAllCliques():
    debugOut = open("debug.txt", "a")    
    
    #The song IDs are setup in order, with some missing in between
    #Step 1: Figure out the max index
    p = ListPageParser()
    p.feed(readPage(LIST_NEW_URL))
    MaxIndex = int(np.max(np.array(p.IDs)))
    printDebugOut("MaxIndex: %i"%MaxIndex, debugOut)
    
    #Step 2: Loop through each index, checking to see if it's already
    #been found in a clique, and if not whether the page actually exists
    cliques = []
    songCliques = {}
    istart = 1
    NYoutube = 0
    if os.path.exists("cache.txt"):
        X = pickle.load(open("cache.txt"))
        istart = X['i']
        cliques = X['cliques']
        songCliques = X['songCliques']
        NYoutube = X['NYoutube']
    for i in range(istart, MaxIndex+1):
        #Backup every 100 songs
        if i%100 == 0:
            printDebugOut("Dumping backup...", debugOut)
            fout = open("cache.txt", "w")
            pickle.dump({'i':i+1, 'cliques':cliques, 'songCliques':songCliques, 'NYoutube':NYoutube}, fout)
            fout.close()
        if i in songCliques:
            printDebugOut("Song with ID %i already in clique %i"%(i, songCliques[i]), debugOut)
            continue
        s = readPage(PERFORMANCE_URL + "%i/versions"%i)
        p = OopsChecker()
        p.feed(s)
        if p.oops:
            printDebugOut("Song with ID %i doesn't exist"%i, debugOut)
            continue
        p = PerformanceParser()
        p.feed(s)
        CliqueNum = len(cliques)
        uniqueClique = True
        for song in p.songs:
            if song["ID"] in songCliques:
                uniqueClique = False
                break
        # This case handles sites with multiple tables (e.g. instrumental and foreign versions) which will 
        # cause the same group of songs to come up twice.  For now not including instrumental and foreign 
        # versions, though this may be of interest later
        if not uniqueClique:
            printDebugOut("The clique on page %i has already appeared somewhere else..."%i, debugOut)
            continue
        for song in p.songs:
            song["CliqueNum"] = CliqueNum
            songCliques[song["ID"]] = CliqueNum
            if song["youtube"]:
                NYoutube += 1
        cliques.append(p.songs)
        printDebugOut("Found clique %i for song %i (%i unique songs so far, %i Youtube)"%(CliqueNum, i, len(songCliques), NYoutube), debugOut)
    return cliques

def TestSong():
    # Testing song with ID 900
    fin = open("Test900.html")
    s = fin.read()
    fin.close()
    s = s.decode('utf8')
    p = PerformanceParser()
    p.feed(s)
    for s in p.songs:
        print(s)

def TestListRecent():
    fin = open("TestListRecent.html")
    s = fin.read()
    fin.close()
    s = s.decode('utf8')
    p = ListPageParser()
    p.feed(s)
    MaxIndex = int(np.max(np.array(p.IDs)))
    print(MaxIndex)

if __name__ == '__main__':
    cliques = getAllCliques()
