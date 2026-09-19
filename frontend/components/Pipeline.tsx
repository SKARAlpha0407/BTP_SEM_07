
import React from 'react';

const steps = ['Query', 'Search', 'Rank', 'Extract', 'Synthesize'];

export default function Pipeline({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex items-center justify-between w-full max-w-2xl mx-auto my-8 px-4">
      {steps.map((step, i) => (
        <React.Fragment key={step}>
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
              i <= currentStep ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
            }`}>
              {i + 1}
            </div>
            <span className={`text-xs mt-2 ${i <= currentStep ? 'text-blue-600 font-medium' : 'text-gray-400'}`}>
              {step}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className={`flex-1 h-0.5 mx-2 transition-colors ${i < currentStep ? 'bg-blue-600' : 'bg-gray-200'}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
