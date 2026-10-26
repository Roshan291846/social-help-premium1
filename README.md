# Social Help Premium — Razorpay Checkout starter

## Included
- Customer registration/login (passwords are hashed)
- Dashboard and help-request form
- Admin request management
- Razorpay Standard Checkout integration for ₹100 per 30 days
- Server-side payment signature verification and captured-payment check

## Important plan behavior
This implementation is **not automatic recurring billing**. It takes one ₹100 payment and grants 30 days; the customer must pay again to extend it. Automatic monthly renewal needs Razorpay Subscriptions/recurring setup and customer consent.

## Run locally
1. Install Python 3.10+.
2. Extract this ZIP and open a terminal in the extracted folder.
3. Install dependencies:
   `pip install -r requirements.txt`
4. Set a Flask secret and Razorpay **Test Mode** API keys as environment variables.

### Windows PowerShell
```powershell
$env:SECRET_KEY="replace-with-a-long-random-secret"
$env:RAZORPAY_KEY_ID="rzp_test_your_key_id"
$env:RAZORPAY_KEY_SECRET="your_test_key_secret"
python app.py
```

### macOS / Linux
```bash
export SECRET_KEY="replace-with-a-long-random-secret"
export RAZORPAY_KEY_ID="rzp_test_your_key_id"
export RAZORPAY_KEY_SECRET="your_test_key_secret"
python app.py
```

5. Open `http://127.0.0.1:5000` in your browser.
6. Register an account, log in, and open the ₹100 subscription page.
7. Test with Razorpay's test mode first. Never put the Key Secret in HTML/JavaScript or commit it to Git.

## Set up Razorpay keys
Create/sign in to your Razorpay account and use its official dashboard to generate **Test Mode** API keys. Official guide:
https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/

The Key ID and Key Secret belong on the server as environment variables. Do not paste keys into a public chat or upload them to public code.

## Admin setup
Register an account first, stop the app, then run:
`python make_admin.py your-email@example.com`
Restart the app and log in.

## Before going live
- Replace Test Mode keys with Live Mode keys only after successful testing and required provider onboarding/verification.
- Deploy with HTTPS and a production WSGI server; set `COOKIE_SECURE=1`.
- Add CSRF protection, rate limiting, privacy policy, terms/refund policy, backups, error monitoring, and verified webhooks for reliable payment reconciliation.
- The app checks the server-side checkout signature and fetches the payment status before activating membership. For robust production billing, also configure and verify Razorpay webhooks.
- Never collect customers' social-media passwords, OTPs, recovery codes, or card details.
- This is an independent help service and is not affiliated with Meta.
