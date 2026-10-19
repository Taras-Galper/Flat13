@echo off
cd /d "C:\Users\grafica\source\repos\dira-landing\blender"
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b dira_mood2.blend -P mood_bake2.py -- 128 160 export >> "C:\Users\grafica\source\repos\dira-landing\mood\bake2_console.log" 2>&1
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b dira_mood2.blend -P mood_bake2.py -- 128 160 morning,midday,dusk >> "C:\Users\grafica\source\repos\dira-landing\mood\bake2_console.log" 2>&1
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b dira_mood2.blend -P mood_bake2.py -- 128 160 entry,walls,media,paper,screen,kitchen >> "C:\Users\grafica\source\repos\dira-landing\mood\bake2_console.log" 2>&1
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b dira_mood2.blend -P mood_bake2.py -- 128 160 corridor,master,bed3,mamad,bed4,terrace >> "C:\Users\grafica\source\repos\dira-landing\mood\bake2_console.log" 2>&1
echo done > "C:\Users\grafica\source\repos\dira-landing\mood\bake2_done.txt"
