import { Metadata } from "next"
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm"

export const metadata: Metadata = {
  title: "Forgot Password | BrandLens",
  description: "Reset your BrandLens password",
}

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />
}
