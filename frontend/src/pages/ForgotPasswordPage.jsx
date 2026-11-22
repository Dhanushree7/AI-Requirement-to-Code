import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Mail, 
  ArrowRight, 
  ArrowLeft, 
  AlertCircle, 
  CheckCircle2, 
  ShieldCheck, 
  Send,
  Info
} from 'lucide-react';
import AuthLayout from '../components/auth/AuthLayout';
import { authApi } from '../api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [successInfo, setSuccessInfo] = useState(null);

  const validateEmail = (val) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
  };

  const handleValidation = () => {
    const newErrors = {};
    if (!email.trim()) {
      newErrors.email = 'Please enter your account email address.';
    } else if (!validateEmail(email)) {
      newErrors.email = 'Please enter a valid work email address (e.g., name@company.com).';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError(null);
    setSuccessInfo(null);

    if (!handleValidation()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await authApi.forgotPassword(email.trim());
      setSuccessInfo({
        message: res.message || 'If an account exists with this email address, a password reset link has been sent. Please check your inbox.',
        email: email.trim()
      });
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'An error occurred while dispatching the reset link. Please try again.';
      setApiError(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout activeTab="forgot-password">
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
            Reset your Password
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Enter your verified work email to receive secure single-use recovery instructions.
          </p>
        </div>

        {/* API Error Notification */}
        {apiError && (
          <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-900 dark:text-rose-200 text-xs flex items-start gap-2.5 animate-in fade-in">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            <div className="leading-relaxed">{apiError}</div>
          </div>
        )}

        {/* Success Confirmation Card */}
        {successInfo ? (
          <div className="p-5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/80 text-emerald-950 dark:text-emerald-200 space-y-4 animate-in fade-in">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
                  Password Reset Dispatched
                </h4>
                <p className="text-xs text-emerald-900 dark:text-emerald-200 leading-relaxed font-medium">
                  {successInfo.message}
                </p>
              </div>
            </div>

            {/* Spam Folder Reminder */}
            <div className="p-3 rounded-xl bg-amber-50/90 dark:bg-amber-950/40 border border-amber-200/80 dark:border-amber-800/60 text-[11px] text-amber-900 dark:text-amber-200 flex items-start gap-2">
              <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <p className="leading-relaxed">
                <strong>Important:</strong> If you don't see the email in your inbox within a few minutes, please check your <strong>spam or junk folder</strong>.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-white/70 dark:bg-emerald-900/30 border border-emerald-200/60 dark:border-emerald-800/50 text-[11px] text-emerald-800 dark:text-emerald-300 space-y-1 font-mono">
              <div>Target: <strong>{successInfo.email}</strong></div>
              <div>Validity: <strong>15 minutes</strong> (Single-use token)</div>
            </div>

            <div className="pt-1 flex items-center justify-between">
              <button
                type="button"
                onClick={() => { setSuccessInfo(null); setEmail(''); }}
                className="text-xs text-emerald-700 dark:text-emerald-400 hover:underline"
              >
                Send another reset link
              </button>
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors"
              >
                <span>Return to Sign In</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        ) : (
          /* Forgot Password Form */
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            
            {/* Email Input */}
            <div className="space-y-1.5">
              <label 
                htmlFor="forgot-email" 
                className="block text-xs font-semibold text-slate-700 dark:text-slate-300"
              >
                Account Work Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="forgot-email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (errors.email) setErrors({ ...errors, email: null });
                  }}
                  placeholder="name@company.com"
                  autoComplete="email"
                  autoFocus
                  className={`w-full pl-10 pr-4 py-2.5 rounded-xl text-xs bg-slate-50 dark:bg-slate-900/60 border ${
                    errors.email 
                      ? 'border-rose-400 dark:border-rose-500 focus:ring-rose-400' 
                      : 'border-slate-200 dark:border-slate-700 focus:border-blue-500 dark:focus:border-blue-400'
                  } text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all`}
                />
              </div>
              {errors.email && (
                <p className="text-[11px] text-rose-600 dark:text-rose-400 flex items-center gap-1 mt-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.email}</span>
                </p>
              )}
            </div>

            {/* Security Assurance Pill */}
            <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-[11px] text-slate-600 dark:text-slate-400">
              <ShieldCheck className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
              <span>We never disclose whether an email is registered to prevent account enumeration.</span>
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
                    <span>Dispatching Reset Link...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Send Reset Link</span>
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
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Sign In</span>
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
