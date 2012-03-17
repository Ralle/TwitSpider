Description:
A Python scraper for Leo Laporte's online podcast / netcast network. It indexes shows and their episodes and can generate RSS feeds from them.
It takes quite a while to index all episodes as there are more than 4000. So I reommend indexing a single show instead or just let it run overnight.

Reason:
So I can listen to the Security Now backlog without needing to manually download each episode. This allows you to subscribe in iTunes to the RSS file you generate if you host it on any HTTP server (I use my Public Dropbox folder).

Usage:
Index list of shows, this is required to do first, otherwise the scraper does not know which shows exist
$ python main.py showlist

Discover all episodes in all shows, indexes the lists of episodes for all shows, but does not get media links and descriptions
$ python main.py shows

Index all episodes in all shows
$ python main.py episodes

If you are only interested in a single show (for example Security Now) you can use the following command
$ python main.py show "Security Now"

Dependencies:
bs4 - http://www.crummy.com/software/BeautifulSoup/
html5lib - http://code.google.com/p/html5lib/
PyRSS2Gen - http://www.dalkescientific.com/Python/PyRSS2Gen.html