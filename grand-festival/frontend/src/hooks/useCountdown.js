import { useEffect, useState } from 'react'
import { FESTIVAL_TARGET_UTC } from '../config.js'

const DEFAULT_TARGET = new Date(FESTIVAL_TARGET_UTC).getTime()

function compute(target) {
  const diff = Math.max(0, target - Date.now())
  return {
    days: Math.floor(diff / 86400000),
    hours: Math.floor((diff % 86400000) / 3600000),
    mins: Math.floor((diff % 3600000) / 60000),
    secs: Math.floor((diff % 60000) / 1000),
    done: diff === 0,
  }
}

export default function useCountdown(target = DEFAULT_TARGET) {
  const [time, setTime] = useState(() => compute(target))
  useEffect(() => {
    const id = setInterval(() => setTime(compute(target)), 1000)
    return () => clearInterval(id)
  }, [target])
  return time
}
