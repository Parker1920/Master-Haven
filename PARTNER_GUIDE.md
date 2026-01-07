# Haven Control Room - User Guide

Welcome to Haven! This guide covers everything you need to know about using the Haven Control Room, whether you're submitting your first discovery or managing a community.

---

## Table of Contents

1. [What is Haven?](#what-is-haven)
2. [For Everyone: Submitting Discoveries](#for-everyone-submitting-discoveries)
3. [For Partners: Community Management](#for-partners-community-management)
4. [For Partner Sub-Admins: Helping Your Community](#for-partner-sub-admins-helping-your-community)
5. [Security & Safety Features](#security--safety-features)
6. [Permissions Quick Reference](#permissions-quick-reference)
7. [FAQ & Troubleshooting](#faq--troubleshooting)

---

## What is Haven?

Haven is a shared database for No Man's Sky discoveries. It allows players and communities to:

- **Submit** star systems, planets, and points of interest
- **Browse** discoveries on an interactive 3D galaxy map
- **Collaborate** with your Discord community

### Access Haven

Open your web browser and go to:

```
https://voyagers-haven-3dmap.ngrok.io
```

---

## For Everyone: Submitting Discoveries

This section is for **all users** - whether you're part of a Discord community or exploring solo. No account required!

### How to Submit a System

#### Step 1: Open the System Wizard

From the homepage, click **"Add System"** or go directly to:
```
https://voyagers-haven-3dmap.ngrok.io/haven-ui/wizard
```

#### Step 2: Enter System Information

**Required Fields (marked with red *):**

| Field | Description |
|-------|-------------|
| **System Name** | The exact name as it appears in-game |
| **Discord Community** | Select your community OR choose "Personal" if you're not affiliated |
| **Your Discord Username** | So we can contact you if needed (e.g., `YourName` or `YourName#1234`) |

**Recommended Fields:**

| Field | Description |
|-------|-------------|
| **Galaxy** | Which galaxy (defaults to Euclid) |
| **Glyph Code** | The 12-character portal address - highly recommended! |
| **Description** | Any notes about the system |

> **Tip:** The glyph code is the most valuable piece of information - it lets others find your system!

#### Step 3: Add Planets (Optional but Recommended)

Click **"Add Planet"** to document planets in the system:

You can include:
- Planet name and type
- Climate/weather conditions
- Flora and fauna levels
- Resources and materials
- Sentinel activity level
- Base locations

#### Step 4: Submit for Approval

When you're ready:

1. Review your information
2. Click **"Submit for Approval"**
3. You'll see a confirmation with your Submission ID

```
System submitted for approval!

Submission ID: 42
System Name: My Cool System

An admin will review your submission.
```

### What Happens After You Submit?

1. Your submission goes into a **review queue**
2. A reviewer from your selected community checks the data
3. Once approved, it appears on the map and in the database!

> **How long does approval take?** Usually within a few hours to a day, depending on your community's activity.

### Choosing the Right Discord Community

When submitting, you must select a Discord community:

| Option | When to Choose |
|--------|----------------|
| **Your Community** (e.g., "IEA", "Galactic Hub") | You're a member of that Discord and submitting on their behalf |
| **Personal** | You're not affiliated with any community, just sharing your discovery |

> **Important:** Only select a community if you're actually part of it. Personal submissions are perfectly welcome!

### Tips for Good Submissions

1. **Double-check the system name** - typos can't be fixed after approval
2. **Include the glyph code** - this is the most useful data for other players
3. **Add planet details** - the more info, the more useful your submission
4. **Use your real Discord username** - so reviewers can contact you with questions

---

## For Partners: Community Management

Partners are **community leaders** who manage their Discord community's presence in Haven. If you run a No Man's Sky Discord community, this section is for you.

### Getting Partner Access

Partner accounts are created by Haven administrators. If you'd like to register your community, contact the Haven team.

### Logging In

1. Go to **Admin Login** or visit:
   ```
   https://voyagers-haven-3dmap.ngrok.io/haven-ui/login
   ```

2. Enter your Partner credentials (username and password)

3. You'll see your community name displayed after login

> **Note:** Sessions expire after 10 minutes of inactivity for security. Just log back in if needed.

### What Partners Can Do

As a Partner, you have elevated privileges for **your community only**:

#### Create Systems Directly

Unlike regular users, your submissions go **straight to the database** - no approval needed!

1. Go to **Add System**
2. Fill out the system information
3. Click **Save** (not "Submit for Approval")

Your systems are automatically tagged with your community.

#### Review & Approve Submissions

Your main job is reviewing submissions from your community members:

1. Go to **Pending Approvals**
   ```
   https://voyagers-haven-3dmap.ngrok.io/haven-ui/approvals
   ```

2. You'll see submissions tagged with your community

3. Click a submission to review the details

4. **Approve** (green button) if everything looks good
   - System immediately goes to the database

5. **Reject** (red button) if there's an issue
   - You must provide a reason so the submitter knows what to fix
   - They can resubmit after making corrections

#### Edit Your Community's Systems

You can edit any system tagged with your community:

1. Find the system in **Systems** list
2. Click **Edit**
3. Make your changes
4. Click **Save**

> **Note:** You cannot edit systems belonging to other communities.

#### Create Sub-Admin Accounts

Need help managing submissions? Create Sub-Admin accounts for trusted community members:

1. Go to **Sub-Admins**
   ```
   https://voyagers-haven-3dmap.ngrok.io/haven-ui/sub-admins
   ```

2. Click **"Create Sub-Admin"**

3. Fill out the form:
   - **Username** - At least 3 characters
   - **Password** - At least 6 characters (share securely with them)
   - **Display Name** - Their name shown in the system
   - **Features** - What they're allowed to do

#### Available Features for Sub-Admins

| Feature | What It Allows |
|---------|----------------|
| **Approvals** | Review and approve/reject submissions |
| **System Create** | Create new systems directly |
| **System Edit** | Edit existing systems |
| **Stats** | View community statistics |
| **Batch Approvals** | Approve/reject multiple submissions at once |

> **Tip:** Start with just "Approvals" and add more features as needed.

#### Managing Sub-Admins

From the Sub-Admins page, you can:

- **Edit** - Change their permissions or display name
- **Reset Password** - If they forget their password
- **Disable** - Temporarily remove access (keeps the account)
- **Delete** - Permanently remove the account

---

## For Partner Sub-Admins: Helping Your Community

Sub-Admins are **community helpers** who assist Partners with managing submissions. If your Partner gave you a Sub-Admin account, this section is for you.

### Logging In

1. Go to **Admin Login**:
   ```
   https://voyagers-haven-3dmap.ngrok.io/haven-ui/login
   ```

2. Enter the credentials your Partner gave you

3. After login, you'll see your name and your community displayed

### What Sub-Admins Can Do

Your abilities depend on what features your Partner enabled for you:

#### If You Have "Approvals" Permission

You can review and approve/reject submissions for your community:

1. Go to **Pending Approvals**

2. Review submissions (same process as Partners above)

3. Approve good submissions, reject problematic ones with a reason

#### If You Have "System Create" Permission

You can create systems directly (they go straight to the database, tagged with your community).

#### If You Have "System Edit" Permission

You can edit existing systems tagged with your community.

### What Sub-Admins Cannot Do

- Create or manage other Sub-Admin accounts (Partner only)
- See or approve submissions from other communities
- Change your own permissions (ask your Partner)
- Approve your own submissions (security feature - see below)

---

## Security & Safety Features

Haven has multiple security measures to ensure data quality and prevent abuse.

### Self-Approval Prevention

**You cannot approve your own submissions.** This applies to Partners AND Sub-Admins.

When viewing a submission you made, you'll see:
- A **"YOUR SUBMISSION"** badge (amber/yellow)
- The Approve and Reject buttons are disabled
- A message explaining you cannot approve your own work

**Why?** This ensures every submission has a second pair of eyes before going into the database. It prevents accidental errors and maintains data quality.

**How does it know it's mine?**
- If you were logged in when you submitted → matched by your account
- If you weren't logged in → matched by your Discord username

> **Example:** If your Partner account is "CoolPartner" and you submit a system with Discord username "CoolPartner#1234", the system recognizes it's the same person and blocks self-approval.

### Audit Logging

**Every action is recorded.** Haven tracks:

- Who approved or rejected each submission
- When the action was taken
- Rejection reasons
- All system edits

This means:
- Full accountability for all decisions
- Disputes can be resolved with clear records
- Community leaders can monitor activity

### Permission Scoping

**You only see your community's data:**

- Partners only see submissions tagged with their community
- Sub-Admins only see submissions based on their Partner's community
- You cannot access other communities' pending queues

### Data Privacy

**Personal information is protected:**

- "Personal" submissions (no community affiliation) only show the Discord username to Haven administrators
- Partners and Sub-Admins see "PERSONAL" tag but not the submitter's Discord info
- IP addresses are logged for security but not displayed to Partners/Sub-Admins

### Session Security

- Sessions expire after **10 minutes of inactivity**
- Passwords are securely hashed (never stored as plain text)
- All connections are encrypted (HTTPS)

---

## Permissions Quick Reference

### Regular Users (No Account)

| Action | Allowed? |
|--------|----------|
| Browse systems and map | Yes |
| Submit systems for approval | Yes |
| Approve/reject submissions | No |
| Edit systems | No |
| Create accounts | No |

### Partners

| Action | Allowed? |
|--------|----------|
| Everything regular users can do | Yes |
| Create systems directly (no approval) | Yes |
| Edit your community's systems | Yes |
| Approve submissions (your community) | Yes |
| Reject submissions (your community) | Yes |
| Approve YOUR OWN submissions | **No** |
| Create Sub-Admin accounts | Yes |
| See other communities' submissions | No |
| Edit other communities' systems | No |

### Partner Sub-Admins

| Action | Allowed? |
|--------|----------|
| Everything regular users can do | Yes |
| Approve submissions (if enabled) | Based on permissions |
| Create systems (if enabled) | Based on permissions |
| Edit systems (if enabled) | Based on permissions |
| Approve YOUR OWN submissions | **No** |
| Create Sub-Admin accounts | No |
| Change your own permissions | No |

---

## FAQ & Troubleshooting

### Submitting Systems

**Q: Do I need an account to submit systems?**
> No! Anyone can submit systems. You just need to provide your Discord username so we can contact you if needed.

**Q: How long until my submission is approved?**
> It depends on your community's activity. Most submissions are reviewed within a few hours to a day.

**Q: Can I edit my submission after sending it?**
> Not directly. If you made a mistake, wait for it to be rejected (with feedback) or contact your community's Partner.

**Q: What if I'm not part of any Discord community?**
> Choose "Personal" as your Discord Community. Your submission will still be reviewed and added to the database.

**Q: Why is my Discord username required?**
> Two reasons: (1) So reviewers can contact you with questions, and (2) To prevent you from approving your own submissions if you later become a Partner/Sub-Admin.

**Q: I submitted to the wrong community. What do I do?**
> Contact the community's Partner or Haven administrators. They can reject it so you can resubmit to the correct community.

### For Partners & Sub-Admins

**Q: I forgot my password. How do I reset it?**
> - **Sub-Admins:** Contact your Partner - they can reset it for you
> - **Partners:** Contact the Haven administrators

**Q: Why can't I approve this submission?**
> Check for these reasons:
> - It's YOUR submission (look for "YOUR SUBMISSION" badge)
> - It belongs to a different community
> - You don't have "Approvals" permission enabled

**Q: I accidentally rejected a good submission. Can I undo it?**
> Rejections can't be undone, but the submitter can resubmit. If it's urgent, contact Haven administrators.

**Q: Why does it say "YOUR SUBMISSION" when I didn't submit this?**
> The system matches by Discord username. If your account username matches the submitter's Discord username (even variations like `User` vs `User#1234`), it's flagged as yours.

**Q: Can I see who submitted what?**
> You can see the Discord username of submitters for your community. For "Personal" submissions, you'll only see "PERSONAL" - the actual username is hidden for privacy.

**Q: I'm a Partner but some features are missing. Why?**
> Some features may be disabled system-wide. Contact Haven administrators if you believe you should have access.

### Technical Issues

**Q: The page isn't loading.**
> Try:
> 1. Refresh the page (Ctrl+F5 or Cmd+Shift+R)
> 2. Clear your browser cache
> 3. Try a different browser
> 4. Check that the URL is correct

**Q: I keep getting logged out.**
> Sessions expire after 10 minutes of inactivity for security. This is normal - just log back in.

**Q: I'm getting an error when submitting.**
> Common causes:
> - Missing required fields (check for red borders)
> - A system with that exact name is already pending
> - Network issues - try again in a moment

**Q: The 3D map isn't working.**
> The map requires WebGL. Try:
> 1. Use a modern browser (Chrome, Firefox, Edge)
> 2. Enable hardware acceleration in browser settings
> 3. Update your graphics drivers

---

## Need Help?

- **Regular Users:** Contact your Discord community's leadership
- **Sub-Admins:** Contact your Partner
- **Partners:** Contact Haven administrators

---

*Thank you for contributing to Haven! Every discovery you share helps build an incredible resource for the No Man's Sky community.*
