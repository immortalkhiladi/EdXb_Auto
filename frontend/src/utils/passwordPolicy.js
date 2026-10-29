// Password policy shared by every form that creates or resets a password.
// The BACKEND (portal/security.py) enforces the same rules and is the authority; this only gives instant feedback.
export const PASSWORD_MIN = 4;
export const PASSWORD_MAX = 6;
export const PASSWORD_HINT = 'Password: 4–6 characters with at least one uppercase letter (A–Z), one number (0–9) and one special character (e.g. @ # $ !).';

const SPECIAL = /[!-/:-@[-`{-~]/; // printable ASCII punctuation

/** One clear sentence per problem; an empty array means the password is acceptable. */
export function passwordProblems(password) {
  const pw = String(password ?? '');
  const problems = [];
  if (pw.length < PASSWORD_MIN || pw.length > PASSWORD_MAX) {
    problems.push(`Password must be ${PASSWORD_MIN} to ${PASSWORD_MAX} characters long (yours has ${pw.length}).`);
  }
  const missing = [];
  if (!/[A-Z]/.test(pw)) missing.push('an uppercase letter (A-Z)');
  if (!/[0-9]/.test(pw)) missing.push('a number (0-9)');
  if (!SPECIAL.test(pw)) missing.push('a special character (for example @, #, $ or !)');
  if (missing.length) problems.push(`Password must include at least one of each: missing ${missing.join(', ')}.`);
  return problems;
}

/** Single message for display, or '' when valid. */
export function passwordError(password) {
  return passwordProblems(password).join(' ');
}
