/**
 * ShiftSelector Component - 班別選擇器
 * 12班制選擇器
 */

import React from 'react';
import { Clock } from 'lucide-react';

interface ShiftSelectorProps {
  selectedShift: string | null;
  onShiftChange: (shiftId: string | null) => void;
  disabled?: boolean;
}

const SHIFTS = [
  { id: '01', number: 1, range: '00:00-02:00', period: '深夜', emoji: '🌙' },
  { id: '02', number: 2, range: '02:00-04:00', period: '深夜', emoji: '🌙' },
  { id: '03', number: 3, range: '04:00-06:00', period: '清晨', emoji: '🌅' },
  { id: '04', number: 4, range: '06:00-08:00', period: '清晨', emoji: '🌅' },
  { id: '05', number: 5, range: '08:00-10:00', period: '上午', emoji: '☀️' },
  { id: '06', number: 6, range: '10:00-12:00', period: '上午', emoji: '☀️' },
  { id: '07', number: 7, range: '12:00-14:00', period: '下午', emoji: '🌤️' },
  { id: '08', number: 8, range: '14:00-16:00', period: '下午', emoji: '🌤️' },
  { id: '09', number: 9, range: '16:00-18:00', period: '傍晚', emoji: '🌆' },
  { id: '10', number: 10, range: '18:00-20:00', period: '傍晚', emoji: '🌆' },
  { id: '11', number: 11, range: '20:00-22:00', period: '夜間', emoji: '🌃' },
  { id: '12', number: 12, range: '22:00-00:00', period: '夜間', emoji: '🌃' },
];

export const ShiftSelector: React.FC<ShiftSelectorProps> = ({
  selectedShift,
  onShiftChange,
  disabled = false
}) => {
  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
      <div className="flex items-center gap-2 mb-4">
        <Clock className="w-5 h-5 text-nook-leaf" />
        <h3 className="text-lg font-bold text-nook-text">選擇班別</h3>
      </div>

      {/* All Shifts Button */}
      <button
        onClick={() => onShiftChange(null)}
        disabled={disabled}
        className={`w-full mb-3 px-4 py-3 rounded-2xl font-medium transition-all ${
          selectedShift === null
            ? 'bg-nook-leaf text-white shadow-lg shadow-nook-leaf/30'
            : 'bg-nook-cream/50 text-nook-text hover:bg-nook-cream'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        🌍 全時段
      </button>

      {/* Shift Grid */}
      <div className="grid grid-cols-2 gap-2">
        {SHIFTS.map((shift) => {
          const isSelected = selectedShift === shift.id;

          return (
            <button
              key={shift.id}
              onClick={() => onShiftChange(shift.id)}
              disabled={disabled}
              className={`px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                isSelected
                  ? 'bg-nook-leaf text-white shadow-md'
                  : 'bg-nook-cream/30 text-nook-text hover:bg-nook-cream/60'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="flex items-center gap-2">
                <span>{shift.emoji}</span>
                <div className="text-left">
                  <div className="font-bold">班別 {shift.id}</div>
                  <div className="text-xs opacity-80">{shift.range}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export { SHIFTS };
