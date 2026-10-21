.syntax unified
.thumb

.equ FORMAT_STOCK, 0x0805761c
.equ FLASH_READ,   0x0803f774
.equ SECTOR_READ,  0x080470ec
.equ STAGE_WRITE,  0x08047148
.equ SECTOR_WRITE, 0x080475d8
.equ DISPATCH_END, 0x0800df33
.equ FLASH_CTX,    0x20001820
.equ STAGE_BASE,   0xc01f0000
.equ PROJECT_BASE, 0x6001fff0

.macro call_abs target
    ldr     r12, =((\target) + 1)
    blx     r12
.endm

.section .text
.balign 4
.global title_hook
.type title_hook,%function
title_hook:
    push    {r4-r7, lr}
    sub     sp, #12             @ 20 + 12 keeps sp 8-byte aligned
    mov     r4, r0
    mov     r5, r1
    mov     r6, r2
    mov     r7, r3
    str     r6, [sp]
    str     r7, [sp, #4]
    ldr     r0, =0x0805ae68
    cmp     r6, r0
    bne     title_fallback
    cmp     r7, #1
    blo     title_fallback
    cmp     r7, #16
    bhi     title_fallback
    cmp     r5, #17
    blo     title_fallback
    subs    r7, #1
    lsl     r7, r7, #17
    ldr     r1, =PROJECT_BASE
    add     r1, r1, r7
    movs    r3, #8
    ldr     r2, =FLASH_CTX
    mov     r0, r2
    mov     r2, r4
    call_abs FLASH_READ
    movs    r6, #0
title_validate:
    ldrb    r0, [r4, r6]
    cmp     r0, #0
    beq     title_valid_end
    cmp     r0, #32
    blo     title_fallback
    cmp     r0, #126
    bhi     title_fallback
    adds    r6, #1
    cmp     r6, #16
    blo     title_validate
title_valid_end:
    cmp     r6, #0
    beq     title_fallback
    movs    r0, #0
    strb    r0, [r4, r6]
    mov     r0, r6
    b       title_return
title_fallback:
    mov     r0, r4
    mov     r1, r5
    ldr     r2, [sp]
    ldr     r3, [sp, #4]
    call_abs FORMAT_STOCK
title_return:
    add     sp, #12
    pop     {r4-r7, pc}
.size title_hook, .-title_hook

.balign 4
.global setname_hook
.type setname_hook,%function
setname_hook:
    @ Replaces mov r2,r7 / mov r1,r4 at 0800df28: r4 already holds the message;
    @ r1 is clobbered on the dispatcher's auto-open-session path.
    push    {r4, lr}
    ldrb    r0, [r4, #8]
    cmp     r0, #0x7c
    bne     setname_fallback
    cmp     r8, #16
    bne     setname_done
    ldrb    r0, [r4, #2]            @ normalized slot (08009048: byte-1); 0..15
    cmp     r0, #15
    bhi     setname_done
    ldrb    r0, [r7]
    cmp     r0, #32
    blo     setname_done
    cmp     r0, #126
    bhi     setname_done
    movs    r1, #1
setname_validate:
    ldrb    r2, [r7, r1]
    cmp     r2, #0
    beq     setname_next
    cmp     r2, #32
    blo     setname_done
    cmp     r2, #126
    bhi     setname_done
setname_next:
    adds    r1, #1
    cmp     r1, #16
    blo     setname_validate

    ldrb    r1, [r4, #2]
    lsl     r1, r1, #17
    ldr     r2, =0x60010000
    add     r1, r1, r2
    movs    r0, #0
    call_abs SECTOR_READ

    sub     sp, #8
    ldr     r0, =STAGE_BASE
    str     r0, [sp]
    movs    r0, #0
    movw    r1, #0xfff0
    mov     r2, r7
    movs    r3, #8
    call_abs STAGE_WRITE
    add     sp, #8

    ldrb    r1, [r4, #2]
    lsl     r1, r1, #17
    ldr     r2, =0x60010000
    add     r1, r1, r2
    movs    r0, #0
    call_abs SECTOR_WRITE
    ldr     r0, =0x20000671
    movs    r1, #0
    strb    r1, [r0]
    b       setname_done

setname_fallback:
    mov     r0, r6
    mov     r1, r4
    mov     r2, r7
    call_abs 0x0800cca8
setname_done:
    pop     {r4, lr}
    ldr     r12, =DISPATCH_END
    bx      r12
.size setname_hook, .-setname_hook

.ltorg
