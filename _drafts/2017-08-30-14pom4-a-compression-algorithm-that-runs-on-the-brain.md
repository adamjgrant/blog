---
layout: post
title: "14POM4: A compression algorithm that runs on the brain"
tags:
 -
---

![“Memories” by Taymaz Valley is licensed under CC BY 2.0](//cdn.everything.io/blog/14pom4/carousel.jpg)
<small>“Memories” by Taymaz Valley is licensed under CC BY 2.0</small>

How much can a human being remember? According to "The Magical Number," in our working memory, it's 7+/-2. [Wikipedia has an article about The Magical Number Seven, Plus or Minus Two](https://en.wikipedia.org/wiki/The_Magical_Number_Seven,_Plus_or_Minus_Two) (7POM2). It's a well known number in psychology circles and is attributed to the cognitive psychologist George A. Miller. This explains to me why I can look at a seven digit phone number and type it in from memory pretty well right away but I somehow struggle with the same task if the area code is included.

# Can memory be hacked?

![“Notes” by INPIVIC Family is licensed under CC BY 2.0](//cdn.everything.io/blog/14pom4/notes.jpg)
<small>“Notes” by INPIVIC Family is licensed under CC BY 2.0</small>

I've felt burdened by this human limitation, especially at work where there's often little time to write things down. When a manager is looking at me in the eye, I want to have an answer ready. So much time and stress is shaved off when I can grab something from my head instead of pushing and pulling data out of tools.

Why couldn’t 7POM2 be hacked? After all, it’s about “objects” in working memory, not individual brain bits. An “object” in memory is a slippery thing. It turns out by digging into this “object” we can expand our memory by orders of magnitude. I’ll show you in this article how I found a way to not only store the ten digit phone number but much larger numbers with very little effort. 

# Hacking the Object

![“VQ7D0108” by United Palace Cathedral is licensed under CC BY 2.0](//cdn.everything.io/blog/14pom4/palace.jpg)
<small>“VQ7D0108” by United Palace Cathedral is licensed under CC BY 2.0</small>

Before I get to 14POM4, some context: I started this train of thought after revisiting the concept of a “Memory Palace,” which goes back as far as Ancient Rome. Memory Palaces were imagined places where the thinker could memorize objects in the Palace to represent different pieces they wished to memorize. The Palace enabled Romans to deliver entire speeches from memory after little time practicing. 

Imagine storing your grocery list in your head. You could have a pair of slippers near the door. They look like loaves of bread. The floor is waxed with butter, the tiles are crackers with red decoration resembling ketchup, etc. It’s a bizarre scene but it makes your list harder to forget than remember. 

This concept is called “Chunking.”  We’ve managed to hack the memory “object” almost by making several objects one. This is quite simply a compression algorithm that works on the brain. 

Another variation of this does away with the palace and requires the memorizer to imagine these objects in harmony in some visual way. For example, maybe the bread is already cut in half, buttered, with crackers and ketchup sandwiched between. It forms a single image that occupies only one of our 7POM2 spots. 

I use these memory tricks almost every day. The only downside is the wait time in running the algorithm. You have to stop to dream up these representations and commit the image to memory. I usually only need 5 minutes to compile everything in my project’s current Jira Sprint, and for me it’s more than worth it. 

# 14POM4

![“V&A Kanban November 19th” by Richard Barrett-Small is licensed under CC BY 2.0](//cdn.everything.io/blog/14pom4/board.jpg)
<small>“V&A Kanban November 19th” by Richard Barrett-Small is licensed under CC BY 2.0</small>

That brings us to my next attempt to push this a little further. Many of my memorization needs are represented in numbers. Each Jira ticket has a unique number on it, so i wanted to find a way to quickly pull these up from memory. On occasion, I needed to store numbers for other ticketing systems that were 8 digits long. This technically lived within the limits of 7POM2, but it’s also in the short-lived space of working memory. I also wanted to memorize my credit cards so I could easily type them in when buying things. My head is probably the most secure place to store something like that. 

## How it works

Unlike the memory palace, my technique is advanced. I don’t say that to flatter myself. I don't like that part about it and It’s a downside to sharing the method to the world. It requires you do a ton of preparation and commit some time into doing so. But once you’ve done that, you have an amazing tool that will keep paying dividends.

I decided to take every number between 1-99 and assign a food image to it. Here's a preview:

|Number|Food|
|---|---|
|1|Banana|
|2|Cherry|
|3|Orange|
|...|...|
|50|Potato|
|51|Noodle|
|52|Rice|
|...|...|
|97|Canteloup|
|98|Pumpkin|
|99|Watermelon|

I had to form a connection between the number and the food strong enough so that I didn't have to dig, as soon as I see a chunk of caramel, I think "42." When I see the number 470110 I immediately think of a fig banana strawberry smoothie. This table not only allows me to store two objects in one, it creates the possibility for meaningful connections between them.

I don't know if 14 plus or minus two is really the upper limit for using this technique, but I doubt it is actually that low. By combining techniques of the memory palace and visualization, I can chunk these assignments further into drawings and put those drawings into different corners of the palace.

Imagine walking into a room and try to remember what I tell you. There is a shelf with a black pepper and whipped-cream topped orange. Got it? Turn your head and see that the rug on the floor is a big leaf of kale with a wine stain and a border made of olives. Got that one too?

You just memorized 204103336193, a twelve digit number with a silly thought. All you were missing was the preparation of these food associations in your long term memory. 

# What I did with my new ability

![“Credit Cards” by Sean MacEntee is licensed under CC BY 2.0](//cdn.everything.io/blog/14pom4/credit.jpg)
<small>“Credit Cards” by Sean MacEntee is licensed under CC BY 2.0</small>

At work, I've taken a habit of committing important Jira tickets to different initiatives my team is working on. This has lead to me imagining strange visualizations a ball of tofu in the shape of an orange sitting inside one of our machines (Ticket JIRA-943 is about that machine). I love being in a meeting and verbally pointing someone to that ticket for details when they ask.

I've memorized all my credit cards. This took me a few repetitions as chunking the 16 digit number with the verification code and expiration date still requires about eleven objects. Putting whipped cream on peanuts and finding a way to combine olives with cinnamon helped to chunk this down a little more.

Just to challenge myself, I've been trying to store the dates of important historical events like Pearl Harbor and The Civil War.

I have a medical bill I've been paying off in several payments as I wait for my flexible spending to refill itself. Every time I call in I have to supply an account number. I've got this memorized as a stack of a few fruits.

## Taking it further.

I'm pretty wiped out after memorizing a spreadsheet with 99 items across two columns. Every once in a while, I forget a number and have to look it up again, but I expect the repetition and continued usage will solidify it.

That being said, I decided to pick a few visualizations to commit to memory to help me chunk patterns in the numbers. Here's a few examples:

|Pattern|Description|Examples|
|---|---|---|
|x sandwich|A number and the same number reversed|Peanut sandwich is 3773<br>wasabi sandwich is 7337<br>banana sandwich is 0110|
|x smoothie|A number followed by itself plus 1|A peanut smoothie is 3738|
|x infused y|A number x interrupted by y and followed by x again|peanut infused banana is 370137|

I've noticed three digit numbers constantly come up as the food representing the first two digits followed by an overused 1-9 food. Instead, I try to just imagine n of the two digit thing. 923 is three bottles of ketchup. 454 is four pineapples, etc.
