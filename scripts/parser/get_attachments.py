#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# File          : get_attachments.py
# Author        : bssthu
# Project       : cyl-eye-770
# Description   : 从邮件中下载附件
# 

import imaplib
import email
import hashlib
from load_parser_config import *


STR_EXCEED_MAX_FILE_NUM = 'exceed max file num to replace'

max_file_num_to_replace = 1    # 替换一定数量的本地文件后不再运行，-1表示无限
file_num_replaced = 0


def get_mail(host, port, user, password, criteria, attachment_path):
    """收取邮件，遍历解析

    Args:
        host: imap 服务器
        port: imap 端口
        user: 用户名
        password: 密码
        criteria: 邮件搜索准则
        attachment_path: 附件存放路径
    """

    # 建立连接
    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
    except Exception as e:
        print('connect failed: %s' % e)
        return

    # 获取列表
    try:
        conn.select('INBOX', False)
        typ, data = conn.search(None, criteria)
        mail_ids = [i for i in data[0].split()]
        mail_ids.reverse()      # 从最新的邮件开始
    except Exception as e:
        print('failed to get mail id: %s' % e)
        return

    # 遍历列表
    parsed_files = []
    exceed_max_file_num = False
    for mail_id in mail_ids:
        try:
            typ, data = conn.fetch(mail_id, 'BODYSTRUCTURE')
            if exists_new_attachment_name(data[0].decode(), parsed_files):
                typ, data = conn.fetch(mail_id, '(RFC822)')
                msg = email.message_from_bytes(data[0][1])
                parse_email_and_save_attachments(msg, attachment_path, parsed_files)   # 解析，下载附件
        except Exception as e:
            print('failed to get attachment(s) from mail %s: %s' % (mail_id, e))
            if str(e) == STR_EXCEED_MAX_FILE_NUM:
                break  # 不再下载
            continue


def exists_new_attachment_name(bodystructure, parsed_files):
    """判断是否存在新附件名

    Args:
        bodystructure: A parsed representation of the [MIME-IMB] body structure
                       information of the message.
        parsed_files: 已下载或检查的附件名
    """
    words = bodystructure.split('"')
    for i in range(0, len(words) - 2):
        if words[i] == 'FILENAME':
            if words[i + 2] not in parsed_files:
                return True
    return False


def parse_email_and_save_attachments(msg, path, parsed_files):
    """解析一封邮件，下载附件。
    若有同名附件，则下载最新。
    若下载前已存在同名文件，则比较，如果不同则覆盖。

    Args:
        msg: 邮件内容
        path: 附件保存路径
        parsed_files: 已下载或检查的附件名
    """

    global max_file_num_to_replace, file_num_replaced

    for part in msg.walk():
        if not part.is_multipart():
            filename = part.get_filename()

            # if is attachment
            if filename is not None:
                # get newest if attachments have same name
                if filename not in parsed_files:
                    parsed_files.append(filename)

                    # download attachment
                    content = part.get_payload(decode=True)
                    file_hash = hashlib.md5(content).hexdigest()

                    # compare
                    abspath = os.path.join(path, filename)
                    if os.path.isfile(abspath):
                        # mark replaced
                        file_num_replaced += 1
                        if file_num_replaced > max_file_num_to_replace >= 0:
                            # 要替换文件数超过限制，则不再替换
                            raise RuntimeError(STR_EXCEED_MAX_FILE_NUM)

                        fp = open(abspath, 'rb')
                        current_hash = hashlib.md5(fp.read()).hexdigest()
                        fp.close()
                        # 去重
                        if file_hash == current_hash:
                            print('skip file %s' % filename)
                            continue

                    # save file
                    try:
                        fp = open(abspath, 'wb')
                        fp.write(content)
                        fp.close()
                        print('save %s' % filename)
                    except IOError as e:
                        print('failed to download file %s: %s' % (filename, e))


def main():
    # config
    configs = load_parser_config()
    if configs is None:
        return
    if 'email' not in configs \
            or 'name' not in configs['email'] \
            or 'password' not in configs['email'] \
            or 'imapServer' not in configs['email']:
        print('missing element(s) in parser config.')
        return None

    port = configs['email'].get('port', 993)
    criteria = configs['email'].get('criteria', 'ALL')
    attachment_path = configs.get('attachmentPath', './')
    global max_file_num_to_replace
    max_file_num_to_replace = configs.get('maxFileNumToReplace', -1)

    # download attachments
    get_mail(configs['email']['imapServer'], port,
             configs['email']['name'], configs['email']['password'],
             criteria, attachment_path)


if __name__ == '__main__':
    main()
