# AWS onboarding checklist

Everything you need to do **before** the AWS deployment work can start.
This covers only the parts that can't be automated — sign-up, account
security, CLI auth, SSH keys.

When you finish each step, tick the box. When you're done with the whole
list, the deployment work I'll drive can begin.

---

## 1. Create the AWS account

- [ ] Visit https://aws.amazon.com/ → **Create an AWS Account**
- [ ] Email address (use one you'll keep — this becomes the root account)
- [ ] Account name (just your name is fine)
- [ ] Verify the email (code sent to your inbox)
- [ ] Strong password (use a password manager — 1Password, Bitwarden, Apple Keychain)
- [ ] **Account type: Personal** (not Business)
- [ ] Real address + phone number
- [ ] **Payment info:** debit/credit card. AWS does a temporary $1 auth charge to verify the card; it's refunded. The Free Tier won't charge you as long as you stay within limits — but you'll never know if you've exceeded them unless you set billing alerts (next section).
- [ ] **Phone verification** — they call or text a code. This usually works reliably; if it doesn't, try the alternative (call vs. text).
- [ ] **Support plan: Basic (Free).** Don't pick Developer or Business plans — those are billed monthly.
- [ ] Sign in to the console at https://console.aws.amazon.com/

---

## 2. Lock down the root account (do this BEFORE anything else)

The "root user" is the email you signed up with. It has unlimited
permissions on the account, including the power to close the account
or change billing. **You should never use it for daily work** — only
for billing changes, account closure, and the initial admin setup
below.

- [ ] **Enable MFA on the root user.**
  - Console → click your name top-right → **Security credentials**
  - Under "Multi-factor authentication (MFA)" click **Assign MFA device**
  - Choose **Authenticator app** (Microsoft Authenticator, Google
    Authenticator, 1Password, Authy — any TOTP app works)
  - Scan the QR code, enter two consecutive 6-digit codes, save
  - **Why this matters:** without MFA, anyone who phishes your password
    owns your account. With MFA, they also need your phone.

- [ ] **Set up a billing alert.**
  - Console search bar → **Billing and Cost Management**
  - Left nav → **Budgets** → **Create budget**
  - **Budget type:** Cost budget
  - **Budgeted amount:** $1 (yes, one dollar — the goal is to be alerted
    *the moment* anything starts costing money, so you can investigate)
  - **Email:** your email
  - **Why this matters:** AWS billing surprises are a meme for a reason.
    A $1 alert catches a misconfigured resource long before it becomes
    a $500 bill.

- [ ] **Sign out of the root account.** From here on, you'll use an IAM
  user (next section).

---

## 3. Create an IAM admin user (your daily-driver login)

Best practice: never log in as root for daily work. Create a separate
"admin" IAM user with administrative permissions, and use that.

- [ ] Sign back in as root (one last time)
- [ ] Console search bar → **IAM** → **Users** → **Create user**
- [ ] **User name:** something like `smrahman-admin` or `dev-admin`
- [ ] Check **Provide user access to the AWS Management Console**
  - Pick **I want to create an IAM user**
  - Set a strong password (different from your root password)
  - Uncheck "Users must create a new password at next sign-in"
- [ ] **Permissions:** **Attach policies directly** → check
  **AdministratorAccess**
  - (Yes, full admin is broader than necessary, but this is your account
    and there's no team. Tighter scoping comes later.)
- [ ] **Create user.** AWS will show you a sign-in URL like
  `https://123456789012.signin.aws.amazon.com/console` — **save it**.
  This is your sign-in URL going forward, not the regular AWS sign-in
  page. (You can also bookmark it.)

- [ ] **Enable MFA on this user too.**
  - Click the new user → **Security credentials** tab → **Assign MFA**
  - Same flow as the root MFA setup.

- [ ] **Sign out of root. Sign in as the IAM admin user** using the URL
  AWS gave you. From here on, this is your everyday account.

---

## 4. Generate programmatic access keys for the CLI

The IAM user needs an **access key** so the AWS CLI on your Mac can
talk to AWS as that user.

- [ ] Signed in as the IAM admin user, top-right → **Security credentials**
- [ ] Scroll to **Access keys** → **Create access key**
- [ ] **Use case:** Command Line Interface (CLI)
- [ ] Acknowledge the recommendation warning, click Next
- [ ] Skip the description tag (or add one like "macbook-cli")
- [ ] **Create access key**
- [ ] **DOWNLOAD THE CSV** or copy both:
  - **Access key ID** (looks like `AKIAIOSFODNN7EXAMPLE`)
  - **Secret access key** (looks like `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)
  - **You will never see the secret key again after this screen.** If
    you lose it, you have to delete and recreate the key. Don't commit
    these to git, don't paste them in chat, don't email them.

---

## 5. Install + configure the AWS CLI on your Mac

- [ ] Install:
  ```bash
  brew install awscli
  ```
- [ ] Verify install:
  ```bash
  aws --version
  ```
  Should print something like `aws-cli/2.x.x`.

- [ ] Configure with the access keys you just downloaded:
  ```bash
  aws configure
  ```
  It'll prompt for four things:
  - **AWS Access Key ID:** paste the AKIA... value
  - **AWS Secret Access Key:** paste the secret
  - **Default region name:** `ca-central-1` (Canada Central, Montreal —
    closest to you, and keeps data residency in Canada)
  - **Default output format:** `json`

- [ ] Confirm it works:
  ```bash
  aws sts get-caller-identity
  ```
  You should see something like:
  ```json
  {
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/smrahman-admin"
  }
  ```
  If the `Arn` ends in your IAM user name (not `:root`), you're
  authenticated correctly.

---

## 6. Generate an SSH key (for EC2 access)

You'll SSH into the EC2 instance to inspect logs, run one-off commands,
etc. This requires an SSH keypair on your Mac. Skip this step if you
already have `~/.ssh/id_ed25519` or `~/.ssh/id_rsa`.

- [ ] Check if you already have one:
  ```bash
  ls ~/.ssh/id_*
  ```
  If you see `id_ed25519` or `id_rsa`, you're done with this section.

- [ ] If you need to generate one:
  ```bash
  ssh-keygen -t ed25519 -C "your_email@example.com"
  ```
  Accept the default path (`~/.ssh/id_ed25519`), set a passphrase if you
  want extra protection.

- [ ] Print the **public** key (this is what gets uploaded to AWS, never
  the private key):
  ```bash
  cat ~/.ssh/id_ed25519.pub
  ```
  Copy the output — you'll paste it into the EC2 launch script later.

---

## 7. Optional but recommended: GitHub repo settings for CI/CD

These come into play when we set up GitHub Actions to auto-deploy.
You don't need to do them yet, but it's good to know they're coming:

- [ ] Confirm your GitHub repo (`smrahman0009/role-tracker-ai`) is the
  one we'll deploy from.
- [ ] Decide whether the repo will stay **public** (best for portfolio)
  or go **private** (more secure but no portfolio visibility). Either
  works for CI/CD.

We'll set up an OIDC federated credential later — that lets GitHub
Actions deploy to AWS without us storing long-lived AWS keys in GitHub
Secrets. No action needed from you on that yet.

---

## When you're done

You should be able to run all of these commands successfully:

```bash
aws --version                    # AWS CLI installed
aws sts get-caller-identity      # Authenticated as your IAM user
cat ~/.ssh/id_ed25519.pub        # SSH public key exists
docker --version                 # Docker still working
docker info | grep "Server Version"  # Docker daemon running
```

Ping me when all six commands succeed and we'll start on
`infra/01-foundations.sh`.

---

## Common pitfalls

**"Verification code never arrives."** AWS sends from
`no-reply-aws@amazon.com`. Check spam, the Promotions tab in Gmail,
and Gmail filters. If still nothing in 15 minutes, hit the Resend link.

**"My credit card was declined."** AWS occasionally flags newer cards
or non-US cards. Try a different card; some banks block international
auth charges by default — call them or use a different one.

**"I see a charge on my card and I'm panicking."** Within $1, that's the
verification auth (always refunded within a few days). Anything else
within free tier should be $0.00. The billing alert from step 2 catches
real charges.

**"`aws sts get-caller-identity` says my IAM user doesn't have
permissions."** Double-check the **AdministratorAccess** policy is
attached. Console → IAM → Users → click your user → **Permissions**
tab — should list `AdministratorAccess`.

**"I lost my access key secret."** Delete the access key in IAM (Security
credentials → Access keys → Actions → Delete) and create a new one.
Then re-run `aws configure`.

**"I want to undo everything."** AWS account deletion is at Account →
Close Account, with a 90-day grace period before final closure. You can
also just stop using the account — there's no cost if no resources are
running.
