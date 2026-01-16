/**
 * TopicSelector Component - 主題選擇器
 * 三大主題選擇
 */

import React from 'react';
import { Target } from 'lucide-react';
import { TopicCode } from '../api/client';

interface TopicSelectorProps {
  selectedTopic: TopicCode;
  onTopicChange: (topic: TopicCode) => void;
  disabled?: boolean;
}

const TOPICS = [
  {
    code: 'DUI' as TopicCode,
    name: '酒駕精準打擊',
    emoji: '🍺',
    color: 'bg-nook-red',
    hoverColor: 'hover:bg-nook-red/80'
  },
  {
    code: 'RED_LIGHT' as TopicCode,
    name: '闖紅燈防制',
    emoji: '🚦',
    color: 'bg-nook-orange',
    hoverColor: 'hover:bg-nook-orange/80'
  },
  {
    code: 'DANGEROUS_DRIVING' as TopicCode,
    name: '危險駕駛防制',
    emoji: '⚡',
    color: 'bg-nook-sky',
    hoverColor: 'hover:bg-nook-sky/80'
  }
];

export const TopicSelector: React.FC<TopicSelectorProps> = ({
  selectedTopic,
  onTopicChange,
  disabled = false
}) => {
  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
      <div className="flex items-center gap-2 mb-4">
        <Target className="w-5 h-5 text-nook-leaf" />
        <h3 className="text-lg font-bold text-nook-text">執法主題</h3>
      </div>

      <div className="space-y-3">
        {TOPICS.map((topic) => {
          const isSelected = selectedTopic === topic.code;

          return (
            <button
              key={topic.code}
              onClick={() => onTopicChange(topic.code)}
              disabled={disabled}
              className={`w-full p-4 rounded-2xl transition-all ${
                isSelected
                  ? `${topic.color} text-white shadow-lg`
                  : `bg-nook-cream/30 text-nook-text ${topic.hoverColor}`
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-12 h-12 ${isSelected ? 'bg-white/20' : topic.color} rounded-xl flex items-center justify-center text-2xl shadow-md`}>
                  {topic.emoji}
                </div>
                <div className="text-left flex-1">
                  <div className="font-bold">{topic.name}</div>
                  <div className={`text-sm ${isSelected ? 'text-white/80' : 'text-nook-text/60'}`}>
                    {topic.code}
                  </div>
                </div>
                {isSelected && (
                  <div className="text-2xl">✓</div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export { TOPICS };
