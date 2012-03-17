import sys, re
from twit_parser import TwitParser

t = TwitParser('twit.sqlite')

# TODO: cannot parse shows with no pagination
# print t.crawl_show_page('http://twit.tv/show/science-news-weekly')

if len(sys.argv) < 2:
  quit("More arguments needed")

if sys.argv[1] == 'debug':
  t.debug()
elif sys.argv[1] == 'showlist':
  t.index_show_list()
elif sys.argv[1] == 'shows':
  t.index_shows()
elif sys.argv[1] == 'episodes':
  t.index_episodes()
elif sys.argv[1] == 'show':
  if len(sys.argv) < 3:
    quit("Missing show argument")
  # security now
  t.index_show_list()
  show = filter(lambda show: show.title == sys.argv[2], t.get_shows())
  if len(show) == 0:
    quit("Show does not exist")
  show = show[0]
  t.index_show(show)
  t.index_episodes(show)
  nam = re.sub('[^a-zA-Z]', '', show.title)
  t.make_rss(show, nam + '.xml')
else:
  print "Unknown command"