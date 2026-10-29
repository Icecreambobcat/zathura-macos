" Isolated VimTeX test configuration; never install as a personal init file.
let s:root = expand('<sfile>:p:h:h')
let s:vimtex = empty($VIMTEX_TEST_RUNTIME)
      \ ? stdpath('data') . '/lazy/vimtex' : $VIMTEX_TEST_RUNTIME
execute 'set runtimepath^=' . fnameescape(s:vimtex)
let g:tex_flavor = 'latex'
let g:vimtex_view_method = 'zathura_simple'
let g:vimtex_compiler_enabled = 0
let g:vimtex_view_enabled = 1
let g:vimtex_cache_root = s:root . '/build/inverse/cache'
let g:zathura_inverse_log = s:root . '/build/inverse/clicks.log'
filetype plugin on
autocmd User VimtexEventViewReverse call writefile(
      \ [v:servername . '|' . expand('%:p') . '|' . line('.') . ':' . col('.')],
      \ g:zathura_inverse_log, 'a')
