---
layout: post
title: "The Puzzle that Infuriated Mathematicians"
tags:
 -
---

From Wikipedia:

"After the problem appeared in Parade, approximately 10,000 readers,
including nearly 1,000 with PhDs, wrote to the magazine, most of them
claiming vos Savant was wrong (Tierney 1991). Even when given explanations,
simulations, and formal mathematical proofs, many people still do not accept
that switching is the best strategy (vos Savant 1991a). Paul Erdős, one of
the most prolific mathematicians in history, remained unconvinced until he
was shown a computer simulation confirming the predicted result (Vazsonyi
  1999)."

This is the story about the Monty Hall Problem. A very simple puzzle of game
show statistics that goes against common sense. I've always liked this problem
but haven't found a way to explain why the answer is what it is until now.

# The problem

![Monty Hall Problem](http://cdn.everything.io/blog/monty-hall/3doors.png)

Suppose you're on a game show, and you're given the choice of three doors:
Behind one door is a car; behind the others, goats. You pick a door, say No. 1,
and the host, who knows what's behind the doors, opens another door, say No. 3,
which has a goat. He then says to you, "Do you want to pick door No. 2?" Is it
to your advantage to switch your choice?

# The solution

You're better off switching every time. 66% of the time you'll get the car.

If you're like me, you expected to get the car only 50% of the time. After all,
one has the goat and one has the car. There's not much more to it than that is
there?

# The explanation

Let's use `G` and `C` to represent cars and goats respectively.

    G  G  C
    –  –  –

Below those doors, let's use `S` for the door you would switch to and `O` for
the door you originally chose.

    G  G  C
    –  –  –
       S  O

In the above example, you would have chosen the car but switched to the goat.

Let's establish one fact that will tie everything together, the door you switch
to will always be the opposite of your choice.

In every case, the doors will look like this:

    G  
    –  –  –
       S  O

Those last two doors are either `G` and `C` or `C` and `G`. There's no other
possible combination.

    G  C  G
    –  –  –
       S  O


    G  G  C
    –  –  –
       S  O

Notice that the `S` door is always the opposite of `O`. Agreed? Let's move on.

You will pick the goat 2/3rds of the time.

          G
    –  –  –
       S  O

          G
    –  –  –
       S  O

          C
    –  –  –
       S  O

The host will reveal a goat door 100% of the time.

    G     G
    –  –  –
       S  O

    G     G
    –  –  –
       S  O

    G     C
    –  –  –
       S  O

And we established that the switch door will always be the opposite of the
original door.

    G  C  G
    –  –  –
       S  O

    G  C  G
    –  –  –
       S  O

    G  G  C
    –  –  –
       S  O

Look down the third column and count how often you end up with the car by
switching...2/3rds of the time. Beautiful, isn't it?
