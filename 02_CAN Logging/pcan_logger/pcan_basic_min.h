/*
 * pcan_basic_min.h  --  a minimal, self-written declaration of the parts of the
 * PEAK-System PCAN-Basic API that the logger uses.
 *
 * The official header (PCANBasic.h) ships with the PCAN-Basic package from
 * https://www.peak-system.com/PCAN-Basic.239.0.html  (Windows) and
 * https://www.peak-system.com/fileadmin/media/linux/index.htm (Linux, "PCAN-Basic
 * for Linux").  If you have it, compile with -DHAVE_PCANBASIC_H and it will be
 * used instead of these declarations.  The two must agree, because both describe
 * the same binary interface exported by PCANBasic.dll / libpcanbasic.so.
 *
 * ENGR 580A2 -- CAN Logging module.
 */
#ifndef PCAN_BASIC_MIN_H
#define PCAN_BASIC_MIN_H

#ifdef HAVE_PCANBASIC_H
#  ifdef _WIN32
#    include <windows.h>
#  endif
#  include "PCANBasic.h"
#else

#include <stdint.h>

#ifdef _WIN32
#  define PCAN_API __stdcall          /* PCANBasic.dll exports WINAPI (stdcall) functions */
#else
#  define PCAN_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Basic type aliases (match the official header) ---------------------- */
typedef uint16_t TPCANHandle;         /* Channel handle, e.g. PCAN_USBBUS1 = 0x51 */
typedef uint32_t TPCANStatus;         /* Error/status code, PCAN_ERROR_xxx        */
typedef uint8_t  TPCANParameter;      /* Parameter id for CAN_Get/SetValue        */
typedef uint8_t  TPCANDevice;         /* Hardware device type                     */
typedef uint8_t  TPCANMessageType;    /* PCAN_MESSAGE_xxx                         */
typedef uint8_t  TPCANType;           /* Non plug-and-play hardware type           */
typedef uint8_t  TPCANMode;
typedef uint16_t TPCANBaudrate;       /* BTR0/BTR1 register value                  */

/* ---- Channel handles ------------------------------------------------------ */
#define PCAN_NONEBUS   0x00
#define PCAN_USBBUS1   0x51
#define PCAN_USBBUS2   0x52
#define PCAN_USBBUS3   0x53
#define PCAN_USBBUS4   0x54
#define PCAN_PCIBUS1   0x41
#define PCAN_PCIBUS2   0x42

/* ---- Baud rates (BTR0BTR1 values for the SJA1000 at 16 MHz) --------------- */
#define PCAN_BAUD_1M     0x0014
#define PCAN_BAUD_500K   0x001C
#define PCAN_BAUD_250K   0x011C   /* SAE J1939 default */
#define PCAN_BAUD_125K   0x031C

/* ---- Status codes --------------------------------------------------------- */
#define PCAN_ERROR_OK           0x00000
#define PCAN_ERROR_XMTFULL      0x00001
#define PCAN_ERROR_OVERRUN      0x00002  /* controller read late -> data lost   */
#define PCAN_ERROR_BUSLIGHT     0x00004
#define PCAN_ERROR_BUSHEAVY     0x00008
#define PCAN_ERROR_BUSOFF       0x00010
#define PCAN_ERROR_ANYBUSERR    (PCAN_ERROR_BUSLIGHT | PCAN_ERROR_BUSHEAVY | PCAN_ERROR_BUSOFF)
#define PCAN_ERROR_QRCVEMPTY    0x00020  /* receive queue empty (not an error)  */
#define PCAN_ERROR_QOVERRUN     0x00040  /* receive queue overrun -> data lost  */
#define PCAN_ERROR_QXMTFULL     0x00080
#define PCAN_ERROR_REGTEST      0x00100
#define PCAN_ERROR_NODRIVER     0x00200
#define PCAN_ERROR_HWINUSE      0x00400
#define PCAN_ERROR_NETINUSE     0x00800
#define PCAN_ERROR_ILLHW        0x01400
#define PCAN_ERROR_ILLNET       0x01800
#define PCAN_ERROR_ILLCLIENT    0x01C00
#define PCAN_ERROR_RESOURCE     0x02000
#define PCAN_ERROR_ILLPARAMTYPE 0x04000
#define PCAN_ERROR_ILLPARAMVAL  0x08000
#define PCAN_ERROR_UNKNOWN      0x10000
#define PCAN_ERROR_INITIALIZE   0x40000

/* ---- Message types -------------------------------------------------------- */
#define PCAN_MESSAGE_STANDARD   0x00
#define PCAN_MESSAGE_RTR        0x01
#define PCAN_MESSAGE_EXTENDED   0x02
#define PCAN_MESSAGE_FD         0x04
#define PCAN_MESSAGE_ERRFRAME   0x40
#define PCAN_MESSAGE_STATUS     0x80

/* ---- Parameters for CAN_GetValue / CAN_SetValue --------------------------- */
#define PCAN_RECEIVE_EVENT      0x03  /* Windows: HANDLE of an event; Linux: int fd for select() */
#define PCAN_MESSAGE_FILTER     0x04
#define PCAN_API_VERSION        0x05
#define PCAN_CHANNEL_VERSION    0x06
#define PCAN_BUSOFF_AUTORESET   0x07
#define PCAN_CHANNEL_CONDITION  0x0A
#define PCAN_RECEIVE_STATUS     0x0F
#define PCAN_ALLOW_STATUS_FRAMES 0x1F
#define PCAN_ALLOW_ERROR_FRAMES 0x20

#define PCAN_PARAMETER_OFF      0x00
#define PCAN_PARAMETER_ON       0x01

/* ---- Structures ----------------------------------------------------------- */
#pragma pack(push, 1)
typedef struct tagTPCANMsg {
    uint32_t         ID;       /* 11 or 29-bit identifier                */
    TPCANMessageType MSGTYPE;  /* PCAN_MESSAGE_xxx                       */
    uint8_t          LEN;      /* data length code 0..8                  */
    uint8_t          DATA[8];  /* payload                                */
} TPCANMsg;

typedef struct tagTPCANTimestamp {
    uint32_t millis;           /* base ms: 0 .. 2^32-1                   */
    uint16_t millis_overflow;  /* roll-arounds of millis                 */
    uint16_t micros;           /* microseconds: 0 .. 999                 */
} TPCANTimestamp;
#pragma pack(pop)

/* ---- Functions ------------------------------------------------------------ */
TPCANStatus PCAN_API CAN_Initialize(TPCANHandle Channel, TPCANBaudrate Btr0Btr1,
                                    TPCANType HwType, uint32_t IOPort, uint16_t Interrupt);
TPCANStatus PCAN_API CAN_Uninitialize(TPCANHandle Channel);
TPCANStatus PCAN_API CAN_Reset(TPCANHandle Channel);
TPCANStatus PCAN_API CAN_GetStatus(TPCANHandle Channel);
TPCANStatus PCAN_API CAN_Read(TPCANHandle Channel, TPCANMsg *MessageBuffer,
                              TPCANTimestamp *TimestampBuffer);
TPCANStatus PCAN_API CAN_Write(TPCANHandle Channel, TPCANMsg *MessageBuffer);
TPCANStatus PCAN_API CAN_GetValue(TPCANHandle Channel, TPCANParameter Parameter,
                                  void *Buffer, uint32_t BufferLength);
TPCANStatus PCAN_API CAN_SetValue(TPCANHandle Channel, TPCANParameter Parameter,
                                  void *Buffer, uint32_t BufferLength);
TPCANStatus PCAN_API CAN_GetErrorText(TPCANStatus Error, uint16_t Language, char *Buffer);

#ifdef __cplusplus
}
#endif

#endif /* HAVE_PCANBASIC_H */
#endif /* PCAN_BASIC_MIN_H */
