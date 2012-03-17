import sqlite3, httplib, re, dateutil.parser, datetime, PyRSS2Gen
from bs4 import BeautifulSoup

def dict_str(d):
  s = ''
  for key in d.keys():
    s += key + ': ' + str(d[key]) + "\n"
  return s

class TwitParser:
  def __init__(self, dbName):
    self.db = sqlite3.connect(dbName)
    def dict_factory(cursor, row):
      d = {}
      for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
      return d
    self.db.row_factory = dict_factory
    self.db.text_factory = str
    self.host = 'twit.tv'
    self.install()
  
  def crawl_shows(self):
    data = self.fetch_page('/shows')
    # begin parsing the contents of the page
    soup = BeautifulSoup(data)
    ul = soup.body.find(id='page').find(id='container').find(id='content-last').find(id='quicktabs_container_3').find(id='quicktabs_tabpage_3_0').ul.find_all('li')
    result = []
    for li in ul:
      is_image = lambda ch: ch.has_key('class') and 'views-field-field-cover-art-fid' in ch['class']
      is_title = lambda ch: ch.has_key('class') and 'views-field-title' in ch['class']
      a = li.find(is_title).a
      show = ShowResult()
      # get the title
      show.title = a.string
      # get the url
      show.uri = a['href']
      # get the image
      show.image = li.find(is_image).find('img')['src']
      result.append( show )
    return result
    
  def crawl_show_uri(self, uri):
    conn = httplib.HTTPConnection(self.host)
    conn.request("HEAD", uri)
    response = conn.getresponse()
    assert response.status == 302
    real_url = response.getheader('location')
    # remove the latest episode number from the URL to get the show page
    real_url = real_url[ 0 : real_url.rfind('/') ]
    # find latest known episode
    return real_url
  
  def crawl_show_page(self, url, page_num = 0):
    data = self.fetch_page(url + '?page=' + str(page_num))
    soup = BeautifulSoup(data)
    # print soup.prettify()
    # get episode list
    episode_list = soup.select('#page #content-last #block-views-show_list-block_1 [class~=view-content] > div')
    # episode_list = soup.select('#page #content-last #block-views-show_list-block_1 .view-content > div')
    # print episode_list
    episodes = []
    for ep in episode_list:
      a = ep.select('a[class~=show-title]')[0]
      episode = EpisodeResult()
      episode.uri = a['href']
      episode.title = a.string
      try:
        episode.description = ep.select('p')[0].string
      except KeyboardInterrupt:
        raise
      except:
        episode.description = unicode(a.next_sibling)
      episode.pubdate = ep.select('[class~=views-field-created] span')[0].string
      episodes.append(episode)
    # get last page
    last_page = soup.select('#block-views-show_list-block_1 [class~=pager] li')[-1].find('a')
    if last_page == None:
      last_page = 0
    else:
      last_page = last_page['href']
      last_page = last_page[ last_page.rfind('=')+1 :]
    # get description of the show
    description = unicode(soup.select('[class~=views-field-field-description-value] p')[0])
    # get big image
    img = soup.select('[class~=views-field-field-cover-art-fid] img')[0]
    image = img['src']
    return {
      'episodes': episodes,
      'lastpage': last_page,
      'description': description,
      'image': image,
    }
  
  def crawl_episode(self, episode):
    data = self.fetch_page(episode.uri)
    soup = BeautifulSoup(data, 'html5lib').select('#content-last')[0]
    episode = EpisodeResult()
    episode.description = unicode(soup.select('[class~=views-field-field-summary-value]')[0])
    links = soup.select('ul[class=download-list]')[0].find_all('li')
    episode.hd_video_url = None
    episode.sd_video_url = None
    episode.sd_video_mobile_url = None
    episode.audio_url = None
    for link in links:
      a = link.span.a
      if a['class'] == 'hd download':
        episode.hd_video_url = a['href']
      elif a['class'] == 'sd download':
        episode.sd_video_url = a['href']
      elif a['class'] == 'sd-low download':
        episode.sd_video_mobile_url = a['href']
      elif a['class'] == 'audio download':
        episode.audio_url = a['href']
    return episode
  
  def index_show_list(self):
    c = self.db.cursor()
    shows = self.crawl_shows()
    for show in shows:
      c.execute('''SELECT * FROM shows WHERE title = ?''', (show.title,))
      show_row = c.fetchone()
      if show_row == None:
        # insert the show
        c.execute('''INSERT INTO shows(uri, title, image) VALUES(?, ?, ?)''', (show.uri, show.title, show.image))
      else:
        c.execute('''UPDATE shows SET image = ? WHERE id = ?''', (show.image, show_row['id']))
    self.db.commit()
    c.close()
  
  def index_show(self, show):
    print "Indexing show:", show.title
    # get proper url
    url = self.crawl_show_uri(show.uri)
    # find latest episode of this show
    c = self.db.cursor()
    c.execute('SELECT * FROM episodes WHERE show=? ORDER BY pubdate DESC LIMIT 1', (show.id,))
    last = c.fetchone()
    # begin indexing
    episodes_to_store = []
    page = 0
    done = False
    while not done:
      print "Page", page
      data = self.crawl_show_page(url, page)
      # set show description
      # if show.description != data['description'] and page == 0:
      c.execute('UPDATE shows SET description=?, image_big=? WHERE id=?', (data['description'], data['image'], show.id))
      show.description = data['description']
      show.image_big = data['image']
      # loop through episodes to insert and detect if we have seen them before
      for episode in data['episodes']:
        if last == None or episode.uri != last['uri']:
          # new episode
          print 'Found episode', episode.title
          episodes_to_store.append(episode)
        else:
          # found old episode
          print "Reached prior episode", episode.title
          done = True
          break
      if page < data['lastpage']:
        page += 1
      else:
        done = True
        print "Reached end"
    # save episodes
    for episode in episodes_to_store:
      c.execute('''INSERT INTO episodes(show, title, short_description, pubdate, uri) VALUES (?,?,?,?,?)''', [show.id, episode.title, episode.description, self.parse_pubdate(episode.pubdate), episode.uri])
    self.db.commit()
    c.close()
  
  def index_shows(self):
    for show in self.get_shows():
      print
      try:
        self.index_show(show)
      except KeyboardInterrupt:
        raise
      except:
        print "Failed to index show"
  
  def index_episodes(self, show = None):
    print "Index episodes"
    # get show episodes
    episodes = self.get_episodes(show)
    # only index episodes that are not indexed
    episodes = filter(lambda ep: ep.description == None, episodes)
    c = self.db.cursor()
    count = len(episodes)
    i = 1
    for episode in episodes:
      print str(i) + '/' + str(count), episode.title
      i += 1
      try:
        r = self.crawl_episode(episode)
        c.execute('''UPDATE episodes 
        SET description = ?, hd_video_url = ?, sd_video_url = ?, sd_video_mobile_url = ?, audio_url = ? WHERE id=?''', 
        [r.description, r.hd_video_url, r.sd_video_url, r.sd_video_mobile_url, r.audio_url, episode.id])
        self.db.commit()
      except KeyboardInterrupt:
        raise
      except:
        print "Failed to index episode"
        print ty
    c.close()
    
  def get_shows(self):
    c = self.db.cursor()
    c.execute('''SELECT * FROM shows''')
    shows = []
    for row in c:
      show = Show(row)
      shows.append(show)
    c.close()
    return shows
  
  def get_episodes(self, show = None):
    c = self.db.cursor()
    if show != None:
      c.execute('''SELECT * FROM episodes WHERE show = ? ORDER BY pubdate DESC''', (show.id,))
    else:
      c.execute('''SELECT * FROM episodes ORDER BY pubdate DESC''')
    episodes = []
    for ep in c:
      episodes.append( Episode(ep) )
    c.close()
    return episodes
  
  def debug(self):
    c = self.db.cursor()
    print 'Shows'
    for show in self.get_shows():
      print show
    print 'Episodes'
    c.execute('''SELECT * FROM episodes''')
    for row in c:
      print dict_str(row)
  
  def fetch_page(self, uri):
    conn = httplib.HTTPConnection(self.host)
    conn.request('GET', uri, headers={
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/534.53.11 (KHTML, like Gecko) Version/5.1.3 Safari/534.53.1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Cache-Control': 'max-age=0'
    })
    response = conn.getresponse()
    if response.status == 404:
      return None
    return response.read()
  
  def parse_pubdate(self, pubdate):
    return dateutil.parser.parse(pubdate).date().isoformat()
  
  def remove_html_script(self, data):
    p = re.compile(r'<script.*?\<\/script>', re.DOTALL)
    return p.sub('', data)
  
  def table_exists(self, name):
    c = self.db.cursor()
    c.execute('''SELECT name FROM sqlite_master 
    WHERE type='table' AND name=?''', (name,))
    fetch = c.fetchone()
    c.close()
    return fetch != None
  
  def install(self):
    c = self.db.cursor()
    if not self.table_exists('shows'):
      # if we have no table, create it
      c.execute('''CREATE TABLE shows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uri TEXT,
        title TEXT,
        image TEXT,
        image_big TEXT,
        description TEXT
      )''')
    if not self.table_exists('episodes'):
      c.execute('''CREATE TABLE episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        show INTEGER,
        title TEXT,
        short_description TEXT,
        description TEXT,
        pubdate INTEGER,
        uri TEXT,
        hd_video_url TEXT,
        sd_video_url TEXT,
        sd_video_mobile_url TEXT,
        audio_url TEXT,
        FOREIGN KEY (show) REFERENCES show(id) ON DELETE CASCADE
      )''')
    # Save (commit) the changes
    self.db.commit()
    # We can also close the cursor if we are done with it
    c.close()
  
  def make_rss(self, show, fileName):
    episodes = self.get_episodes(show)
    items = []
    for episode in episodes:
      items.append(PyRSS2Gen.RSSItem(
        title = episode.title,
        link = episode.audio_url,
        enclosure = PyRSS2Gen.Enclosure(episode.audio_url, 0, "audio/mpeg"),
        description = episode.description,
        guid = PyRSS2Gen.Guid(episode.uri),
        pubDate = dateutil.parser.parse(episode.pubdate)
      ))
    rss = PyRSS2Gen.RSS2(
      title = show.title + " Backlog",
      link = 'http://' + self.host + show.uri,
      description = show.description,
      image = PyRSS2Gen.Image(url = show.image_big, title = '', link = 'http://' + self.host + show.uri),
      lastBuildDate = datetime.datetime.utcnow(),
      items = items
    )
    rss.write_xml(open(fileName, "w"))  

class ShowResult:
  def __str__(self):
    return str(self.__dict__)
  def __repr__(self):
    return self.__str__()

class EpisodeResult:
  def __str__(self):
    return str(self.__dict__)
  def __repr__(self):
    return self.__str__()

class Show:
  def __init__(self, row):
    self.title = row['title']
    self.uri = row['uri']
    self.image = row['image']
    self.image_big = row['image_big']
    self.id = row['id']
    self.description = row['description']
  def __str__(self):
    return dict_str(self.__dict__)
  def __repr__(self):
    return self.__str__()

class Episode:
  def __init__(self, row):
    self.id = row['id']
    self.show = row['show']
    self.title = row['title']
    self.short_description = row['description']
    self.description = row['description']
    self.pubdate = row['pubdate']
    self.uri = row['uri']
    self.hd_video_url = row['hd_video_url']
    self.sd_video_url = row['sd_video_url']
    self.sd_video_mobile_url = row['sd_video_mobile_url']
    self.audio_url = row['audio_url']
  def __str__(self):
    return dict_str(self.__dict__)
  def __repr__(self):
    return self.__str__()