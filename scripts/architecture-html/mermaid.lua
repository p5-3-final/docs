-- ```mermaid 코드 블록을 <pre class="mermaid">로 바꿔 브라우저의 Mermaid JS가 그리게 한다.
function CodeBlock(el)
  if el.classes:includes("mermaid") then
    local esc = el.text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
    return pandoc.RawBlock("html", '<pre class="mermaid">' .. esc .. '</pre>')
  end
end
