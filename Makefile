test:
	mkdir -p test
	touch test/__init__.py
	cp -rf /usr/lib/plexmediaserver/Resources/Plug-ins/Scanners.bundle/Contents/Resources/Common/* test/
	python -m unittest aniMess