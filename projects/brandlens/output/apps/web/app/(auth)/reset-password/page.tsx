import { Metadata } from "next"
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm"

export const metadata: Metadata = {
  title: "Reset Password | BrandLens",
  description: "Set a new password for your BrandLens account",
}

export default function ResetPasswordPage() {
  return <ResetPasswordForm />
}
