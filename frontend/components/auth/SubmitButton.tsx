"use client";

import { Button } from "../../components/ui/Button";
import { Loader2 } from "lucide-react";

interface SubmitButtonProps {
  isLoading: boolean;
  children: React.ReactNode;
}

export function SubmitButton({ isLoading, children }: SubmitButtonProps) {
  return (
    <Button 
      type="submit" 
      className="w-full h-12 text-base font-semibold" 
      disabled={isLoading}
    >
      {isLoading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          <span>Please wait...</span>
        </>
      ) : (
        children
      )}
    </Button>
  );
}
