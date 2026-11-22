import React, { useState, useEffect } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { 
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  AlertCircle, 
  CheckCircle2, 
  ShieldCheck, 
  Clock, 
  KeyRound
} from 'lucide-react';
import AuthLayout from '../components/auth/AuthLayout';
import { authApi } from '../api';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  // Token Verification States
  const [isVerifying, setIsVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [tokenError, setTokenError] = useState(null);
  const [maskedEmail, setMaskedEmail] = useState('');

  // Form Fields
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Submission States
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [resetSuccess, setResetSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setIsVerifying(false);
      setTokenValid(false);
      setTokenError('No password reset token was provided in the URL. Please request a new link.');
      return;
    }

    let isMounted = true;
    authApi.verifyResetToken(token)
      .then((res) => {
        if (!isMounted) return;
        setTokenValid(true);
        setMaskedEmail(res.masked_email || '');
        setIsVerifying(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setTokenValid(false);
        const detail = err.response?.data?.detail;
        const msg = typeof detail === 'string' ? detail : 'This password reset link is invalid, expired, or has already been used.';
        setTokenError(msg);
        setIsVerifying(false);
      });

    return () => { isMounted = false; };
  }, [token]);

  const handleValidation = () => {
    const newErrors = {};

    if (!newPassword) {
      newErrors.newPassword = 'New password is required.';
    } else if (newPassword.length < 8) {
      newErrors.newPassword = 'Password must be at least 8 characters long.';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your new password.';
    } else if (confirmPassword !== newPassword) {
      newErrors.confirmPassword = 'Passwords do not match.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError(null);

    if (!handleValidation()) {
      return;
    }

    setIsSubmitting(true);
    try {
      await authApi.resetPassword(token, newPassword);
      setResetSuccess(true);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : 'Failed to reset password. The link may have expired.';
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout activeTab="reset-password">
      <div className="space-y-6">
        {/* Card Header */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-xs shadow-xs">
              R+C
            </div>
            <div>
              <span className="font-bold text-slate-900 dark:text-white text-base">ReqToCode AI</span>
            </div>
          </div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white pt-1">
            Create a New Password
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Choose a strong password with at least 8 characters.
          </p>
        </div>

        {/* Verifying Token State */}
        {isVerifying && (
          <div className="p-8 text-center space-y-3">
            <div className="w-8 h-8 border-3 border-blue-600/30 border-t-blue-600 rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Verifying security token...
            </p>
          </div>
        )}

        {/* Invalid or Expired Token State */}
        {!isVerifying && !tokenValid && (
          <div className="p-5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-950 dark:text-rose-200 space-y-4 animate-in fade-in">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-rose-500/20 text-rose-600 dark:text-rose-400 shrink-0">
                <Clock className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-bold uppercase tracking-wider text-rose-800 dark:text-rose-300">
                  Link Invalid or Expired
                </h4>
                <p className="text-xs text-rose-900 dark:text-rose-200 leading-relaxed">
                  {tokenError || 'This reset link has expired or was already used.'}
                </p>
              </div>
            </div>

            <div className="pt-2 flex items-center gap-3">
              <Link
                to="/forgot-password"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold transition-colors"
              >
                <span>Request New Reset Link</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                to="/login"
                className="text-xs text-rose-700 dark:text-rose-400 hover:underline"
              >
                Return to Sign In
              </Link>
            </div>
          </div>
        )}

        {/* Successful Reset State */}
        {!isVerifying && tokenValid && resetSuccess && (
          <div className="p-5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/80 text-emerald-950 dark:text-emerald-200 space-y-4 animate-in fade-in">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
                  Password Updated Successfully
                </h4>
                <p className="text-xs text-emerald-900 dark:text-emerald-200 leading-relaxed">
                  Your password has been changed securely and the recovery token has been retired. You can now sign in with your new credentials.
                </p>
              </div>
            </div>

            <div className="pt-2">
              <Link
                to="/login"
                className="w-full py-2.5 px-4 rounded-xl font-semibold text-xs text-white bg-emerald-600 hover:bg-emerald-700 transition-colors flex items-center justify-center gap-2 shadow-md shadow-emerald-600/20"
              >
                <span>Sign In with New Password</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        )}

        {/* Active Reset Password Form */}
        {!isVerifying && tokenValid && !resetSuccess && (
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            
            {/* Associated Account Pill */}
            {maskedEmail && (
              <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400">
                <KeyRound className="w-4 h-4 text-blue-600 shrink-0" />
                <span>Resetting password for: <strong className="font-mono text-slate-800 dark:text-slate-200">{maskedEmail}</strong></span>
              </div>
            )}

            {/* API Error Notification */}
            {apiError && (
              <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-900 dark:text-rose-200 text-xs flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                <div className="leading-relaxed">{apiError}</div>
              </div>
            )}

            {/* New Password Input */}
            <div className="space-y-1.5">
              <label 
                htmlFor="reset-new-password" 
                className="block text-xs font-semibold text-slate-700 dark:text-slate-300"
              >
                New Password <span className="font-normal text-slate-400">(min. 8 characters)</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="reset-new-password"
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    if (errors.newPassword) setErrors({ ...errors, newPassword: null });
                  }}
                  placeholder="Enter new password"
                  autoComplete="new-password"
                  autoFocus
                  className={`w-full pl-10 pr-10 py-2.5 rounded-xl text-xs bg-slate-50 dark:bg-slate-900/60 border ${
                    errors.newPassword 
                      ? 'border-rose-400 dark:border-rose-500 focus:ring-rose-400' 
                      : 'border-slate-200 dark:border-slate-700 focus:border-blue-500 dark:focus:border-blue-400'
                  } text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors cursor-pointer"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {errors.newPassword && (
                <p className="text-[11px] text-rose-600 dark:text-rose-400 flex items-center gap-1 mt-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.newPassword}</span>
                </p>
              )}
            </div>

            {/* Confirm Password Input */}
            <div className="space-y-1.5">
              <label 
                htmlFor="reset-confirm-password" 
                className="block text-xs font-semibold text-slate-700 dark:text-slate-300"
              >
                Confirm New Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <input
                  id="reset-confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (errors.confirmPassword) setErrors({ ...errors, confirmPassword: null });
                  }}
                  placeholder="Re-enter new password"
                  autoComplete="new-password"
                  className={`w-full pl-10 pr-10 py-2.5 rounded-xl text-xs bg-slate-50 dark:bg-slate-900/60 border ${
                    errors.confirmPassword 
                      ? 'border-rose-400 dark:border-rose-500 focus:ring-rose-400' 
                      : 'border-slate-200 dark:border-slate-700 focus:border-blue-500 dark:focus:border-blue-400'
                  } text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors cursor-pointer"
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {errors.confirmPassword && (
                <p className="text-[11px] text-rose-600 dark:text-rose-400 flex items-center gap-1 mt-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.confirmPassword}</span>
                </p>
              )}
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className={`w-full py-2.5 px-4 rounded-xl font-semibold text-xs text-white transition-all flex items-center justify-center gap-2 shadow-md shadow-blue-500/20 ${
                  isSubmitting
                    ? 'bg-blue-400 cursor-not-allowed opacity-80'
                    : 'bg-blue-600 hover:bg-blue-700 active:scale-[0.99] cursor-pointer'
                }`}
              >
                {isSubmitting ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Updating Password...</span>
                  </>
                ) : (
                  <>
                    <span>Confirm & Reset Password</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* Back to Sign In Link */}
        <div className="text-center pt-2">
          <Link
            to="/login"
            className="text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            Cancel and Return to Sign In
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
