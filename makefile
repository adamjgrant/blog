build:
	@echo "Updating rubygems"
	@gem update --system
	@echo "Install dev tools"
	#@xcode-select --install
	@echo "Installing Jekyll"
	@gem install jekyll
	@echo "Updating Kickstart Submodule"
	@git submodule update --recursive --init
	@git submodule update
	@bundle
	# @echo "Installing kickstart dependencies"
	# @cd kickstart;make setup
	@gem install thor
