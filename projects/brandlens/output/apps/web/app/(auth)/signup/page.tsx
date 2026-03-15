import { Metadata } from "next"
import { SignupForm } from "@/components/auth/SignupForm"

export const metadata: Metadata = {
  title: "Sign Up | BrandLens",
  description: "Create a new BrandLens account",
}

export default function SignupPage() {
  return <SignupForm />
}
