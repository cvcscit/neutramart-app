"use client";

import { Suspense } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

function LoginForm({ className }: { className?: string }) {
  const { handleLoginSuccess } = useAuth();
  const navigate = useNavigate();

  function onSuccess(response: any) {
    try {
      handleLoginSuccess(response);
      toast.success("Login successful!");
      navigate("/dashboard");
    } catch (error) {
      toast.error("Login failed.");
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-3xl font-bold">Login to your account</h1>
        <p className="text-muted-foreground text-sm text-balance">
          Use your Google account to sign in
        </p>
      </div>

      <div className="grid gap-6">
        <div className="after:border-border relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t">
          <span className="bg-background text-muted-foreground relative z-10 px-2">
            Continue with
          </span>
        </div>

        <div className="flex justify-center">
          <GoogleLogin onSuccess={onSuccess} />
        </div>
      </div>
    </div>
  );
}

function LoginPageComponent() {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">
            <LoginForm />
          </div>
        </div>
      </div>
      <div className="bg-muted relative hidden lg:block">
        <img
          src="https://i.pinimg.com/1200x/54/01/11/54011192d84bdda594bf2bba0c1b0b6e.jpg"
          alt="Image"
          className="absolute inset-0 h-full w-full object-cover dark:brightness-[0.2] dark:grayscale"
        />
      </div>
    </div>
  );
}

export default function Login() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <LoginPageComponent />
    </Suspense>
  );
}
