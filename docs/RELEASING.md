# Making a release

1. **Push this repository to GitHub** (once): create an empty repository named `MVP05-Plus` on github.com (no README), then in this folder:
   ```
   git remote add origin https://github.com/<you>/MVP05-Plus.git
   git push -u origin main
   ```
   If you'd rather show it as a fork of Mad Dog's repository, fork his on GitHub first and push to your fork instead.
2. **Build the release tools:** on GitHub, open *Actions → release tools → Run workflow*. When it finishes, download its two artifacts, `MVP-Installer` and `gcbridge`, and unzip them.
3. **Build the game** on your PC as the README says (`Build-Source.cmd`), and copy Mad Dog's three VC runtime DLLs (`msvcp140.dll`, `vcruntime140.dll`, `vcruntime140_1.dll`) from his Public Beta package.
4. **Put the zip together:** gather those files in one folder (`MVP05.exe`, `d3dcompiler_ms.dll`, the three DLLs, `MVP-Installer.exe`, `gcbridge`), then:
   ```
   python tools/make_release.py <that folder> "Beta 1"
   ```
   Check the zip has no `assets` files besides `PUT-GAME-FILES-HERE.txt`, and no `gc_icons` or `ps2_icons`.
5. **Publish:** on GitHub, *Releases → Draft a new release*, tag `beta-1`, title `MVP05-Plus Beta 1`, paste `RELEASE-NOTES.md` as the description, attach `MVP05-Plus-Beta-1.zip`, and tick *Set as a pre-release*.
