# Publish UIsername on GitHub

Suggested repository: https://github.com/stagedivepov/UIsername

## 1. Create the repository

1. Sign in to GitHub and open https://github.com/new.
2. Choose `stagedivepov` as the owner and `UIsername` as the repository name.
3. Suggested description: `Free desktop username generator and checker — 18 platforms, 7 languages.`
4. Select **Public** so everyone can view the code and download releases.
5. Leave README and .gitignore initialization disabled: both are included in the prepared source package.
6. Click **Create repository**.

The project does not currently include a license for the application's own code. Third-party vocabulary and icon licenses are documented separately; no MIT license badge has been added.

## 2. Upload the source

Extract `UIsername-source-v2.0.zip`. Upload the contents of the extracted `UIsername` folder as the repository root, including `core/`, `platforms/`, `ui/`, `tests/`, `scripts/`, `docs/`, `.github/`, and the root files.

Using GitHub Desktop:

1. Choose **File → Clone repository → URL** and enter `https://github.com/stagedivepov/UIsername`.
2. Clone it to a local folder.
3. Copy the extracted source contents into that folder, preserving its `.git` directory.
4. Commit the changes with a message such as `Initial release: UIsername v2.0`.
5. Click **Push origin**, or **Publish branch** if shown for the first push.

The README already contains your GitHub username. Its logo and screenshot require `ui/logo.svg` and `docs/interface.jpg` from the source package.

Keep executables in Releases. Do not upload personal `settings.json`, `proxies.txt`, `Names/`, `crash.log`, `.env`, `build/`, or `dist/`.

## 3. Publish the Windows download

1. Open your repository's **Releases** section and choose **Draft a new release**.
2. Create the tag `v2.0` from the branch containing your uploaded source.
3. Use the title `UIsername v2.0 — Windows`.
4. Attach `UIsername.exe`, `UIsername-Windows-x64-v2.0.zip`, and `SHA256SUMS.txt` from the prepared distribution.
5. Add release notes, then click **Publish release**.

Suggested release notes:

> Free username generation and checking for Windows 10/11 x64. Download UIsername.exe and double-click to start. No Python installation required. Choose your language on first launch. Settings and results are stored in your own Windows account. Some platform checks require your own API credentials.

The README's latest-release link will work after a public release has been published.

## 4. Future releases with GitHub Actions

The **Build Windows** workflow supports manual runs and Git pushes of `v*` tags. It is configured to run tests, build the executable, and upload artifacts. Tag pushes also create a draft Release. Review the workflow result and draft before publishing.

When creating a Release manually through GitHub's website, attach the prepared binaries yourself. The workflow's tag trigger uses the push event; publishing a Release through the website is not its configured trigger.

Official guides:

- https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- https://docs.github.com/en/desktop/adding-and-cloning-repositories/cloning-and-forking-repositories-from-github-desktop
- https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
