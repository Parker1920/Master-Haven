    try:
            
            async with session.get(
                f"{BASE}/api/systems/search?q={glyph}&limit=1",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                results = data.get("results", [])
                
                if results:
                    return results[0]  
                return None
    
        except asyncio.TimeoutError:
            print(f"TIMEOUT: glyph lookup for {glyph}")
            return None
    
        except Exception as e:
            print(f"ERROR: glyph lookup for {glyph} -> {e}")
            return None