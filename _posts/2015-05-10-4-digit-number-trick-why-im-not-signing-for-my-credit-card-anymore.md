---
layout: post
title: "4 digit number trick: Why I'm not signing for my credit card anymore"
tags:
 -
---

tl;dr: Instead of my signature, I write a four digit code that is different for every transaction but comes from the same formula every time.

# How many times has this happened to you?

You're at the checkout, swipe your card, and the cashier points to this clunky
little screen attached to a flimsy plastic pen, asking you to draw your
signature into what resembles the display on a basic calculator. You start to
sign and immediately notice the line you are drawing in no way matches up to
the tip of your plastic wand.

LCD credit card signatures are a joke. The whole idea of a signature is to
prevent forgery. When signing with an actual pen on actual paper, there are a
myriad of ways we encode the uniqueness of our being in the strokes on the
paper.

In actual cases of forgery and identity theft, a victim can defend themselves
via a handwriting expert from the inconsistency of the forger's attempted
signature. To the untrained eye, the forger's signature may look similar enough
to the victim's. However, an expert will notice where the victim lifts the pen,
at what angle they hold it, the speed in which they make certain strokes, the
direction in which they cross the "t" or draw the "s". Suffice it to say there
is a hidden, highly unique fingerprint in every human being's signature.

When we leave our signatures using paper and a writing instrument, we
unknowingly reproduce a highly identifiable personal code in the form of strokes,
angles, lifts, and spins. LCD signature displays? Give me a break.

# I'm done signing at the register. Here's what I do instead.

I take identity theft seriously and I'm just fed up with putting false hope into
these little displays. Recently I took an interest in [Public-Key Cryptography](http://en.wikipedia.org/wiki/Public-key_cryptography), but mostly
the basic idea that you could carry around a special code as a "key" (Much like
  a key you would use to open your house) yet have no problem with anyone seeing it.

So I thought about how I might apply this (in a much more simplified way) to my
everyday credit card transactions. Here's what I do now:

*Note: The specific formula I actually use is obviously different because I
wouldn't publish the real one, but the concept is still the same*

Instead of my signature, I write a four digit code that is **different for every
transaction** but comes from **the same formula every time.**

First, I take the first two digits of the price, the two digits of the day and
add one to each digit (Sounds complex but it's actually easy...).

    Charge: $48.21
    Date: April 5, 2015

So that's `5916` (`48` from the price, `05` from the day, each digit incremented
  by `1`.)

# You call that security?

"Are you kidding me? That formula is so simple anyone could reverse-engineer it."
True. But they'd need to see multiple receipts to deduce it correctly whereas with
a signature you'd only need one. Of course, I could make my formula more complicated
but it all depends on how involved you want it to be every time you check out.
This formula is easy enough that I can do it in my head right at the checkout.

Why do this? If I ever need to prove that one "signature" is not mine, I can
easily demonstrate that I follow a pattern for all my transactions. I can reveal
my formula on a need-to-know basis and continue using a new one thereafter.

But yes, it's not airtight but it's fine as a proof-of-concept. I could otherwise
download some SHA-1 generator on my phone and use the first four digits from the
output as my code.

For example, we'll do the same thing without the extra step of adding 1 to each
digit.

    48 from the price
    05 from the date

    4805 in a SHA-1 is b707c6ddb2ac80c9bced5daa5def738068799b41

So the code is

    B707

We could even blend the initial variables (date and price) before hashing.

     4821 (Price)
    +0405 (MM/DD Date)
    -----
     5226 (Total)

And taking the first four of the SHA1 gives us

    1C02

Admittedly, it's quite a bit more involved, but apps could be developed that
could easily generate this for you based on your own customizations.

If such an app were to be distributed to the world, it might make more sense that
each user has their own private key they set which adds to the price and hashes.

     4821 (Price)
    +6829 (User's private key, same one used every time.)
    -----
    11650 (Total)

Once again taking the first four of the SHA1:

    EEF5

The unidirectionality of the SHA-1 (and the fact we don't know which part of it
we're using) is the secret sauce here. `11650` isn't enough because the price
is essentially a known precursor to the public key.  With just two receipts, you
could pull `6829` out of them quite easily. The SHA1 makes it very difficult to
get back to `11650` in the first place.

# How does this help the cashier, who checks the signature?

You're kidding right? Have you ever seen a cashier actually do this?

You have? Wow. That's rare. Okay, so sign your name next to the number.

# How is this better than a signature?

It is a signature. Writing your name is only one form. Anything that uniquely ties
the document back to your execution is a signature. Fingerprints, DNA, passwords,
these are all signatures with varying degrees of security.

And it might **not** be better than a written signature written with a pen. Again,
this is specifically aimed as a solution to those Etch-a-Sketchy low res LCD
displays.
