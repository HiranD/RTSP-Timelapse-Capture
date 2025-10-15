# Push to GitHub and Create Release

## 📦 Repository: https://github.com/HiranD/RTSP-Timelapse-Capture

Your remote is already configured! Follow these steps when you have network connectivity:

---

## 🚀 Step 1: Push All Commits

```bash
cd /c/Users/wande/Documents/RSTP

# Verify remote is correct
git remote -v
# Should show: origin https://github.com/HiranD/RTSP-Timelapse-Capture.git

# Push all commits to GitHub
git push origin main
```

**Expected Output:**
```
Enumerating objects: XX, done.
Counting objects: 100% (XX/XX), done.
Delta compression using up to N threads
Compressing objects: 100% (XX/XX), done.
Writing objects: 100% (XX/XX), XXX KiB | XXX MiB/s, done.
Total XX (delta XX), reused XX (delta XX)
To https://github.com/HiranD/RTSP-Timelapse-Capture.git
   xxxxxxx..xxxxxxx  main -> main
```

---

## 🏷️ Step 2: Create and Push Version Tag

```bash
# Create annotated tag for v2.0.0
git tag -a v2.0.0 -m "Release v2.0.0 - Video Export Feature"

# Verify tag was created
git tag -l

# Push the tag to GitHub
git push origin v2.0.0
```

**Expected Output:**
```
Enumerating objects: 1, done.
Counting objects: 100% (1/1), done.
Writing objects: 100% (1/1), XXX bytes | XXX KiB/s, done.
Total 1 (delta 0), reused 0 (delta 0)
To https://github.com/HiranD/RTSP-Timelapse-Capture.git
 * [new tag]         v2.0.0 -> v2.0.0
```

---

## 📋 Step 3: Create GitHub Release

### Method 1: Via GitHub Website (Recommended)

1. **Navigate to Releases:**
   - Go to: https://github.com/HiranD/RTSP-Timelapse-Capture/releases
   - Click "Draft a new release" or "Create a new release"

2. **Fill in Release Details:**

   **Choose a tag:** `v2.0.0` (should appear in dropdown after pushing tag)

   **Release title:** `v2.0.0 - Video Export Feature`

   **Description:** Copy and paste from `RELEASE_NOTES_v2.0.0.md` file

3. **Upload Release Asset:**
   - Drag and drop or click "Attach binaries"
   - Upload: `release/RTSP_Timelapse_v2.0.0_Windows.zip` (58 MB)
   - Wait for upload to complete (may take 2-3 minutes)

4. **Publish:**
   - ✅ Check "Set as the latest release"
   - ✅ Check "Create a discussion for this release" (optional)
   - Click "Publish release"

---

### Method 2: Via GitHub CLI (Alternative)

If you have GitHub CLI installed:

```bash
# Login to GitHub (if not already)
gh auth login

# Create release with file upload
gh release create v2.0.0 \
  release/RTSP_Timelapse_v2.0.0_Windows.zip \
  --title "v2.0.0 - Video Export Feature" \
  --notes-file RELEASE_NOTES_v2.0.0.md \
  --repo HiranD/RTSP-Timelapse-Capture
```

---

## 📝 Commits Being Pushed

You'll be pushing these 9 commits:

```
ae96889 - Add release packaging and build infrastructure
bde782e - Update README with video export features (v2.0.0)
0ffbfd6 - Add Phase 3.5 completion summary documentation
d0cabfc - Add comprehensive video export test suite
d73c73e - Integrate video export with tabbed interface
ca8ef1a - Add video export panel GUI component
e3331a6 - Add video export controller for business logic
9715e69 - Add preset manager for video export settings
5faa7b4 - Add FFmpeg wrapper for video encoding
```

---

## 📦 Release Asset Details

**File to Upload:**
- **Filename:** `RTSP_Timelapse_v2.0.0_Windows.zip`
- **Location:** `release/RTSP_Timelapse_v2.0.0_Windows.zip`
- **Size:** 58 MB
- **Contains:**
  - RTSP_Timelapse.exe (59 MB standalone executable)
  - README.md (full documentation)
  - QUICKSTART.txt (quick start guide)
  - requirements.txt (for source users)

---

## ✅ Verification Checklist

After creating the release, verify:

- [ ] Release appears at: https://github.com/HiranD/RTSP-Timelapse-Capture/releases
- [ ] Tag `v2.0.0` is visible
- [ ] Release is marked as "Latest"
- [ ] ZIP file is attached and downloadable
- [ ] Release notes are displayed correctly
- [ ] Download link works: `https://github.com/HiranD/RTSP-Timelapse-Capture/releases/download/v2.0.0/RTSP_Timelapse_v2.0.0_Windows.zip`

---

## 🎯 Post-Release Tasks

### 1. Update Repository Settings

Go to: https://github.com/HiranD/RTSP-Timelapse-Capture/settings

**About Section (right sidebar):**
- Description: "Professional RTSP timelapse capture and video export system"
- ✅ Use existing topics or add:
  - `python`
  - `tkinter`
  - `rtsp`
  - `timelapse`
  - `video-export`
  - `ffmpeg`
  - `opencv`
  - `gui-application`
  - `windows`

### 2. Update README Badge (Already Done!)

The version badge in README.md will automatically show v2.0.0

### 3. Test Download

- Download the ZIP from GitHub releases
- Test on a different machine if possible
- Verify executable runs without Python installed

### 4. Announce Release

**GitHub Discussion:**
- Create announcement in Discussions tab
- Link to release

**Social Media (Optional):**
- Share on relevant communities
- Reddit: r/Python, r/timelapse
- Twitter/X with repository link

---

## 🐛 Troubleshooting

### Issue: Push failed - Authentication

```bash
# Use GitHub personal access token
# Go to: https://github.com/settings/tokens
# Generate token with 'repo' scope
# Use token as password when pushing
```

### Issue: Tag already exists

```bash
# Delete local tag
git tag -d v2.0.0

# Delete remote tag (if pushed)
git push origin :refs/tags/v2.0.0

# Recreate tag
git tag -a v2.0.0 -m "Release v2.0.0 - Video Export Feature"
git push origin v2.0.0
```

### Issue: Large file upload timeout

If ZIP upload times out:
1. Check internet connection
2. Try uploading during off-peak hours
3. Consider uploading via GitHub CLI
4. Split release notes into smaller sections

### Issue: "Connection refused" or network errors

- Check internet connectivity
- Verify GitHub is accessible: https://github.com
- Try again after a few minutes
- Check firewall/proxy settings

---

## 📞 Need Help?

**GitHub Docs:**
- [Creating releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [Git basics](https://git-scm.com/book/en/v2/Getting-Started-Git-Basics)

**Your Repository:**
- Main: https://github.com/HiranD/RTSP-Timelapse-Capture
- Releases: https://github.com/HiranD/RTSP-Timelapse-Capture/releases
- New Release: https://github.com/HiranD/RTSP-Timelapse-Capture/releases/new

---

## 🎉 Success!

Once completed, your release will be live at:

**Download URL:**
```
https://github.com/HiranD/RTSP-Timelapse-Capture/releases/download/v2.0.0/RTSP_Timelapse_v2.0.0_Windows.zip
```

**Release Page:**
```
https://github.com/HiranD/RTSP-Timelapse-Capture/releases/tag/v2.0.0
```

Share this URL with users who want to download your timelapse application! 🚀

---

**Created:** October 15, 2025
**Repository:** https://github.com/HiranD/RTSP-Timelapse-Capture
**Version:** 2.0.0
