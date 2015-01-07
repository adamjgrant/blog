---
layout: post
title: "Add Kickstart into a Jekyll 2 Project"
categories: tech
 -
---

1. Start a new Jekyll project following the directions at [Jeykllrb.com](http://jekyllrb.com)
2. Run `git submodule add https://github.com/ajkochanowicz/kickstart.git _kickstart`
3. Open _config.yml and add the following:

    sass:
      load_paths:
        - "_sass"
        - "_kickstart"
        - "_kickstart/lib-core/sass"

4. Open css/main.scss and add this just below the `@charset "utf-8";` line:
  - `@import "lib/sass/themes/default/theme.sass";`

You can now add any Kickstart CSS you want to files imported from css/main.scss

If you're feeling daring, wipe out main.scss completely except for that `@import` line you added.
You'll be running pure Kickstart, but will have to redesign your site a bit.
