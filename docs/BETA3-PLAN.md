# MVP05-Plus Beta 3: plan

What's planned for Beta 3, with what's already known. Beta 2 was released on 2026-11-13.

## Player of the day
Done in Beta 2.1 (tools/installer/potd.py): local date, counted from 2026-11-13 through a SHA-256 shuffle of all the players (each once per round of 731 days); the 30 franchises' default rosters in database/database.big with a picture in frontend/portrait.big (named by playerattrib_audioid), 731 players. The notes below were the plan.

A card across the empty bottom of the *Play* tab: a player's picture, name, team and position (maybe a line of ratings or 2004 stats), a different player each day and the same one for everyone.
- **Pick:** take a fixed hash of the date (for example SHA-256 of `2027-03-14`), modulo the number of eligible players. Don't use a random generator, whose output can change between Python versions. Decide whether the date is local (changes at each player's midnight) or UTC (changes for everyone at the same moment).
- **Players:** the disc's default MLB rosters (the same for everyone), sorted by player id. Never the player's own saves, which drift with trades, imports and edits. Only MLB rosters, and only players with a picture.
- **Picture:** read from the player's own installed game files at run time, like the title art. EA's art is never shipped. First, find where MVP 2005 keeps player headshots in its `.big` files and in what texture format, and whether every MLB player has one. That needs a listing of `assets\data` and a few `.big` files from a real install.
- **Layout:** the dog easter egg uses the bottom-right corner, so leave room for it or let it sit on top of the card.

## Owner mode imports
Import owner mode saves from the PS2, GameCube, PC and Xbox, as dynasties are now. Owner mode is its own mode with its own save type. It needs matched pairs: a new owner mode save with the same team on each platform, saved straight away.

## Budget changer (dynasty)
Every team has a budget in dynasty mode. In a save, org record halfword s21 is the budget in $100K units (FORMAT_NOTES 3.7). In memory, no stored value turned up (it's probably computed), so editing the save may be the way. Needs the other money figures from the budget screen. tywiggins' ChangeMoney is for owner mode and goes with the owner mode work.

## Also open
- **Stamina Changer:** tywiggins' spot (data + 0x231420) holds heap headers on the Xbox, so it needs its own search.
- **GameCube dynasty converter:** history merge by overlap rather than by year (see the save conversion notes, 4.4).
- **Dynasty export to GameCube** from the Launcher (the converter already does it).
- **Low latency for MVP06-Plus;** MVP 2004.
