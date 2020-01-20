test:
	mkdir -p test
	touch test/__init__.py
	cp -rf /usr/lib/plexmediaserver/Resources/Plug-ins/Scanners.bundle/Contents/Resources/Common/* test/
	python -m unittest aniMess

install:
	rm -f /var/lib/plexmediaserver/Library/Application\ Support/Plex\ Media\ Server/Scanners/Series/aniMess.pyc
	install -g plex -o plex -D aniMess.py /var/lib/plexmediaserver/Library/Application\ Support/Plex\ Media\ Server/Scanners/Series/aniMess.py