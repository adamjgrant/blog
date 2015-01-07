build:
	@echo "Installing Jekyll"
	@gem install jekyll
	@echo "Updating Kickstart Submodule"
	@git submodule update
	@echo "Installing kickstart dependencies"
	@cd kickstart;make setup
