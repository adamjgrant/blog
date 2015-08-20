---
layout: post
title: "A different approach to frontend testing"
tags:
 -
---

I was recently pondering an alternative to frontend testing, which I find to be very clunky today.

Typically the way frontend testing works is:

1. A headless browser is launched
2. The browser loads up separate files with instructions on where to navigate or click and which tests to run
3. The test returns the results.

My alternative is

1. Tests are written directly in the code, and are *always* run, even in production with actual users.
   Essentially, this turns testing into browser monitoring as well.
2. The headless browser doesn't read any tests. It just navigates through different websites and clicks on various things.
3. Instead of outputting the results of a text file, it simply outputs the JavaScript console.

# An example of this implementation:

Say you had a button that will pull down the number of members from a database.

    myButton.addEventListener('click', () => {
      getData('/members', () => {
        alert("Data retrieved.");
      });
    });

    var getData = (url) => {
      req = new XMLHttpRequest();
      req.open('GET', url, true);
      req.onload = () => {
      
      };
      req.send();
    }

We can add a test to this


    myButton.addEventListener('click', () => {

      testRunner.specs.getMembersSpec = testRunner.assert("Data is returned in less than 1 second", 1000);

      getData('/members', () => {
        alert("Data retrieved.");
      });
    });

    var getData = (url) => {
      req = new XMLHttpRequest();
      req.open('GET', url, true);
      req.onload = () => {
        
        testRunner.specs.getMembersSpec(true);

      };
      req.send();
    }

Or maybe we want to make sure a certain number of members are returned each time.

    myButton.addEventListener('click', () => {
      testRunner.specs.getMembersSpec = [
        testRunner.assert("Data is returned in less than 1 second", 1000),

        testRunner.expect(
          "Data is returned in less than 1 second", 
          (members) => {
            members > 1;
          }
        )

      ];

      getData('/members', () => {
        alert("Data retrieved.");
      });
    });

    var getData = (url) => {
      req = new XMLHttpRequest();
      req.open('GET', url, true);
      req.onload = () => {
        var data = JSON.parse(response);

        testRunner.specs.getMembersSpec([true, [data.members]]);

      };
      req.send();
    }

We can both run a test via the command line to see the output of these test, but we also have the ability to 
see alerts via a reporting system like Mixpanel or Airbrake when the app is not working as we'd expect for a user.
