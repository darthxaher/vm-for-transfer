#!/usr/bin/python
# coding=utf-8
# -*- encoding: utf-8 -*-

from pprint import pprint
from expatparser import ExpatParser
from parentrecord import ParentRecord
from callstack import CallStack

# clip, lit-tag need special handling if inside of any of these tags
delayed_tags = ['let', 'modify-case']

DEBUG_MODE = False
 
        
class EventHandler(object):
    def __init__(self, compiler):
        self.compiler = compiler
        self.callStack = self.compiler.callStack
        self.codestack = self.compiler.codestack
        self.labels = self.compiler.labels
        
    # list of 'starting' event handlers
    def handle_cat_item_start(self, event):
        def_cat = self.callStack.getTop(2)
        def_cat_id = def_cat.attrs['n']
        if def_cat_id not in self.compiler.def_cats.keys():
            self.compiler.def_cats[def_cat_id] = []

        # lemma is OPTIONAL in DTD
        if 'lemma' in event.attrs.keys():
            regex = event.attrs['lemma']
        else:
            regex = '\w'

        # tags is REQUIRED in DTD
        # but still for safety we're checking
        if 'tags' in event.attrs.keys():
            tags = event.attrs['tags'].split('.')
            for tag in tags:
                # FIXME: what to do in case of empty tags?
                if tag == '':
                    continue
                if tag == '*':
                    regex = regex + '\\t'
                    continue
                regex = regex + '<' + tag + '>'
        else:
            regex = regex + '\t'

        self.compiler.def_cats[def_cat_id].append(regex)

    def handle_attr_item_start(self, event):
        def_attr = self.callStack.getTop(2)
        def_attr_id = def_attr.attrs['n']
        if def_attr_id not in self.compiler.def_attrs.keys():
            self.compiler.def_attrs[def_attr_id] = []

        tags = event.attrs['tags'].split('.')
        regex = ''
        for tag in tags:
            regex = regex + '<' + tag + '>'

        self.compiler.def_attrs[def_attr_id].append(regex)

    def handle_def_var_start(self, event):
        vname = event.attrs['n']
        value = event.attrs.setdefault('v', '')
        self.compiler.variables[vname] = value

    def handle_list_item_start(self, event):
        def_list = self.callStack.getTop(2)
        def_list_id = def_list.attrs['n']

        if def_list_id not in self.compiler.def_lists.keys():
            self.compiler.def_lists[def_list_id] = []
        self.compiler.def_lists[def_list_id].append(event.attrs['v'])

    def handle_def_macro_start(self, event):
        # FIXME later, the macro mode
        self.macroMode = True
        
        macro_name = event.attrs['n']
        npar = int(event.attrs['npar'])
        label = 'macro_' + macro_name + '_start'

        # print macro_name
        self.labels.append(label)
        code = [label + ':	nop']
        self.codestack.append([self.callStack.getLength(), 'def-macro', code])

    # WORKING
    def handle_choose_start(self, event):
        ## print event
        ## a = self.compiler.symbolTable.getChilds(event)
        ## print a
        pass
        
    def handle_when_start(self, event):
        self.compiler.whenid += 1
        self.compiler.whenStack.append(self.compiler.whenid)
        
        label = u'when_' + str(self.compiler.whenStack[-1]) + u'_start'
        self.labels.append(label)
        code = [label + ':	nop']
        self.codestack.append([self.callStack.getLength(), 'when', code])

    def handle_otherwise_start(self, event):
        self.compiler.otherwiseStack.append(self.compiler.otherwiseid)
        label = u'otherwise_' + str(self.compiler.otherwiseStack[-1]) + u'_start'
        self.labels.append(label)
        code = [label + ':	nop']
        self.codestack.append([self.callStack.getLength(), 'otherwise', code])

    def __get_xml_tag(self, event):
        tag = '<' + event.name
        for attr in event.attrs.keys():
            tag +=  ' ' + attr + '="' + event.attrs[attr] + '"'
        tag += '/>'
        return tag

    def __get_clip_tag_basic_code(self, event):
        code = []
        regex = ''
        
        if event.attrs['part'] not in ['lem', 'lemh', 'lemq', 'whole', 'tags']:
            # does optimization help? need to check that
            regex = reduce(lambda x, y: x + '|' + y, self.compiler.def_attrs[event.attrs['part']])
        else:
            # FIXME: the regex might not work
            if event.attrs['part'] == 'lem':
                regex = '\w'
            elif event.attrs['part'] == 'lemh':
                regex = '^\w'            
            elif event.attrs['part'] == 'lemq':
                regex = '#(\s\w)+'            
            elif event.attrs['part'] == 'whole':
                regex = '\\h'            
            elif event.attrs['part'] == 'tags':
                regex = '\\t'

        if DEBUG_MODE:
            code.append(u'### DEBUG: ' + self.__get_xml_tag(event))
        # push pos
        code.append(u'push\t' + event.attrs['pos'])
        # push regex
        code.append(u'push\t' + regex)

        return code

    def __get_clip_tag_lvalue_code(self, event):
        # rvalue code, we want to 'write' new value into clip
        code = []
        if event.attrs['side'] == 'sl': code.append(u'storesl')
        elif event.attrs['side'] == 'tl': code.append(u'storetl')
        return code
    
    def __get_clip_tag_rvalue_code(self, event):
        # rvalue code, we want to 'read' clip's value
        code = []
        if event.attrs['side'] == 'sl': code.append(u'clipsl')
        elif event.attrs['side'] == 'tl': code.append(u'cliptl')
        return code
    
    def handle_clip_start(self, event):
    #def handle_clip_start(self, event, internal_call = False, called_by = None):        
        if True in map(self.compiler.callStack.hasEventNamed, delayed_tags):
            # silently return, when inside delayed tags
            return

        code = self.__get_clip_tag_basic_code(event)

        # code for lvalue or rvalue calculation (i.e. 'clip' mode or 'store' mode)
        #parent =  self.compiler.callStack.getTop(2)
        # NOTE: siblings also include the curret tag
        #siblings =  self.compiler.parentRecord.getChilds(parent)
        
        # normal rvalue mode, we read clip's code
        ## if event.attrs['side'] == 'sl': code.append(u'clipsl')
        ## elif event.attrs['side'] == 'tl': code.append(u'cliptl')
        code.extend(self.__get_clip_tag_rvalue_code(event))
        
        self.codestack.append([self.callStack.getLength(), 'clip', code])

        # other misc tasks
        self.__check_for_append_mode()

    def __get_lit_tag_basic_code(self, event):
        code = []
        if DEBUG_MODE:
            code.append(u'### DEBUG: ' + self.__get_xml_tag(event))
        code.append(u'push\t' + '<' + event.attrs['v'] + '>')        
        return code

    def handle_lit_tag_start(self, event):
        if True in map(self.compiler.callStack.hasEventNamed, delayed_tags):
            return
        code = self.__get_lit_tag_basic_code(event)
        self.codestack.append([self.callStack.getLength(), 'lit-tag', code])

        # other misc tasks
        self.__check_for_append_mode()
        

    def __get_lit_basic_code(self, event):
        # FIXME: fix the problem with empty lit e.g. <lit v=""/>
        # print 'DEBUG push', event.attrs['v'].encode('utf-8')
        code = []
        if DEBUG_MODE:
            code.append(u'### DEBUG: ' + self.__get_xml_tag(event))        
        code.append(u'push\t' + event.attrs['v'])
        return code
    
    def handle_lit_start(self, event):
        if True in map(self.compiler.callStack.hasEventNamed, delayed_tags):
            return        
        code = self.__get_lit_basic_code(event)
        self.codestack.append([self.callStack.getLength(), 'lit-tag', code])

        # other misc tasks
        self.__check_for_append_mode()


    def __get_var_basic_code(self, event):
        code = []
        if DEBUG_MODE:
            code.append(u'### DEBUG: ' + self.__get_xml_tag(event))                
        code.append(u'pushv\t' + event.attrs['n'])
        return code
    
    def handle_var_start(self, event):
        if True in map(self.compiler.callStack.hasEventNamed, delayed_tags):
            return       
        code = self.__get_var_basic_code(event)
        self.codestack.append([self.callStack.getLength(), 'var', code])

    def handle_append_start(self, event):
        self.compiler.APPEND_MODE = True
        code = []
        if DEBUG_MODE:
            code.append(u'### DEBUG: ' + self.__get_xml_tag(event))
        code.append(u'push\t' +  event.attrs['n'])
        self.codestack.append([self.callStack.getLength(), 'append', code])
    

    # list of 'ending' event handlers
    def handle_and_end(self, event, codebuffer):
        codebuffer.append(u'and')

    def handle_or_end(self, event, codebuffer):
        codebuffer.append(u'or')

    def handle_not_end(self, event, codebuffer):
        codebuffer.append(u'not')

    def handle_equal_end(self, event, codebuffer):
        try:
            if event.attrs['caseless'] == 'yes':
                codebuffer.append(u'cmpi')
        except KeyError:
            codebuffer.append(u'cmp')
        
    def handle_begings_with_end(self, event, codebuffer):
        #codebuffer.append('#dummy begins-with')
        pass

    def handle_ends_with_end(self, event, codebuffer):
        #codebuffer.append('#dummy ends-with')
        pass

    def handle_contains_substring_end(self, event, codebuffer):
        #codebuffer.append('#dummy contains_substring')
        pass

    def handle_in_end(self, event, codebuffer):
        pass

    def handle_def_macro_end(self, event, codebuffer):
        label = u'macro_' + event.attrs['n'] + u'_end'
        codebuffer.append(label + '\t:ret')
        self.labels.append(label)
        self.macroMode = False

    def handle_choose_end(self, event, codebuffer):
        childs = self.compiler.symbolTable.getChilds(event)
        ## pprint(childs)
        ## pprint(codebuffer)
        ## print

        has_otherwise = False
        for child in reversed(childs):
            if child.name == 'otherwise':
                has_otherwise = True
                break
        
        # reversing does not take much CPU time, so this is the preferred method over
        # iterating in reverse
        if has_otherwise:
            codebuffer.reverse()
            for index, line in enumerate(codebuffer):
                if line.startswith('#!#jmp\t'):
                    codebuffer[index] = line.replace('#!#jmp\t', 'jmp\t')
                    break
            codebuffer.reverse()
        
        
    def handle_when_end(self, event, codebuffer):
        code = []
        
        local_whenid = self.compiler.whenStack[-1]
        otherwise_end_label = u'otherwise_' + str(local_whenid)  + u'_end'
        when_end_label = u'when_' + str(local_whenid) + u'_end'
        
        self.labels.append(when_end_label)

        code.append('#!#jmp\t' + otherwise_end_label)
        code.append(when_end_label + ':\tnop')
        codebuffer.extend(code)
        
        #self.compiler.whenid += 1

        # set the otherwiseid, if there is actually any otherwise following this when
        # the otherwiseid will be used
        self.compiler.otherwiseid = local_whenid
        self.compiler.whenStack.pop()

    def handle_otherwise_end(self, event, codebuffer):
        label = u'otherwise_' + str(self.compiler.otherwiseStack[-1]) + u'_end'
        
        self.labels.append(label)
        codebuffer.append(label + ':\tnop')
        
        self.compiler.otherwiseStack.pop()

    def handle_test_end(self, event, codebuffer):
        # FIXME: this will probably not work in case of nested 'when' and 'otehrwise'
        # need to find something more mature
        codebuffer.append(u'jnz	when_' + str(self.compiler.whenStack[-1]) + '_end')


    # the followings are delayed mode tags
    def handle_let_end(self, event, codebuffer):
        #child1, child2 = self.compiler.parentRecord.getChilds(event)
        # EXPERIMENTAL
        child1, child2 =  self.compiler.symbolTable.getChilds(event)
        code = []
        if child1.name == 'clip':
            code = self.__get_clip_tag_basic_code(child1)
            if child2.name == 'lit-tag':
                code.extend(self.__get_lit_tag_basic_code(child2))
            elif child2.name == 'lit':
                code.extend(self.__get_lit_basic_code(child2))
            elif child2.name == 'var':
                code.extend(self.__get_var_basic_code(child2))
            elif child2.name == 'clip':
                code.extend(self.__get_clip_tag_basic_code(child2))
                # normal rvalue cliptl or clipsl for 'clip'
                code.extend(self.__get_clip_tag_rvalue_code(child2))
                

            # storetl or storesl
            code.extend(self.__get_clip_tag_lvalue_code(child1))

        if child1.name == 'var':
            # 'var' here is lvalue, so need special care
            code.append('push\t' + child1.attrs['n'])
            if child2.name == 'clip':
                code.extend(self.__get_clip_tag_basic_code(child2))
                # normal rvalue cliptl or clipsl for 'clip'
                code.extend(self.__get_clip_tag_rvalue_code(child2))
            elif child2.name == 'lit-tag':
                code.extend(self.__get_lit_tag_basic_code(child2))
            elif child2.name == 'lit':
                code.extend(self.__get_lit_basic_code(child2))
            elif child2.name == 'var':
                code.extend(self.__get_var_basic_code(child2))

            # now the extra instuction for the assignment
            code.append(u'storev')
            

        codebuffer.extend(code)

    def handle_modify_case_end(self, event, codebuffer):
        ## child1, child2 = self.compiler.parentRecord.getChilds(event)
        code = []
        ## print child1
        ## print child2

    def handle_append_end(self, event, codebuffer):
        
        codebuffer.append(u'push\t' + str(self.compiler.appendModeArgs))
        codebuffer.append(u'appendv')

        # reset the state variables regarding append mode
        self.compiler.appendModeArgs = 0
        self.compiler.APPEND_MODE = False

    def __check_for_append_mode(self):
        if self.compiler.APPEND_MODE == True:
            self.compiler.appendModeArgs += 1

    def handle_concat_end(self, event, codebuffer):
        pass
    
class SymbolTable(object):
    def __init__(self, callStack):
        self.symbolList = {}
        self.childList = {}

        self.currentSymbolId = 0

        self.callStack = callStack

    def addSymbol(self, event):
        # symbol id starts from 1
        self.currentSymbolId += 1        
        self.symbolList[self.currentSymbolId] = event

        currentParentId = -1
        try: currentParent = self.callStack.getTop(2)
        except: currentParent = None
        currentParentId = self.__getId(currentParent)

        if currentParentId not in self.childList.keys():
            self.childList[currentParentId] = []
        self.childList[currentParentId].append(self.currentSymbolId)

    def __getId(self, event):
        eventId = -1
        # this is only for safety, most of the time eventId would be
        # equal to currentSymbolId
        for i in range(self.currentSymbolId, 0, -1):
            if self.symbolList[i] == event:
                return i
        return eventId
            

    def getChilds(self, event):
        eventId = self.__getId(event)
        ## print event
        ## print eventId
        ## pprint(self.childList)
        ## pprint(self.symbolList)
        ## print self.symbolList[719]
        childs = []
        for childId in self.childList[eventId]:
            childs.append(self.symbolList[childId])
        return childs
        

class Compiler(object):
    """
    This is actually a container class that abstracts the underlying logic
    for the compilation process
    """
    def __init__(self, xmlfile):
        # various lists
        self.def_cats = {}
        self.def_attrs = {}
        self.variables = {}
        self.def_lists = {}

        self.labels = []
        self.codestack = []

        # id variables use for labeling, these need to be incremented
        self.whenid = 0
        # otherwiseid, calculated from whenid but initially set to 0
        self.otherwiseid = 0

        # state variables
        self.MACRO_MODE = False
        
        self.APPEND_MODE = False
        self.appendModeArgs = 0

        self.NESTED_WHEN_MODE = False
        
        # data structures
        # whenstack is used for nested when call
        self.whenStack = []
        self.otherwiseStack = []
        
        # callStack holds the call history
        self.callStack = CallStack()
        # parentRecord holds the child parent relationship
        ## self.parentRecord = ParentRecord()
        self.symbolTable = SymbolTable(self.callStack)

        # create the parse and the handler
        self.parser = ExpatParser(xmlfile, self)
        self.eventHandler = EventHandler(self)

        self.processedCode = []

    def compile(self):
        self.parser.parse()

    def optimize(self):
        if len(self.codestack) == 1:
            for line in self.codestack[0][2]:
                line = line.encode('utf-8')

                # optimization 1: remove placeholder instructions (#!#)
                ## if line.startswith('#!#'):
                ##     continue
                
                self.processedCode.append(line)
        else:
            raise CompilerException("FATAL ERROR: Cannot optimize code, the code did not compile correctly!")

        
    def printCode(self):
        for line in self.processedCode:
            print line
            
    def printLabels(self):
        for label in self.labels:
            print label

class CompilerException(Exception):
    pass

if __name__ == '__main__':
    inputfile = 'input-compiler/set1.t1x'
    #inputfile = 'apertium-en-ca.en-ca.t1x'

    try:
        compiler = Compiler(inputfile)
        compiler.compile()
        compiler.optimize()
        #print compiler.def_cats
        #print compiler.variables
        #print compiler.def_attrs
        #print compiler.def_lists
        compiler.printCode()
        #compiler.printLabels()

        #print compiler.symbolTable.symbolList
        #pprint(compiler.symbolTable.childList)
    except CompilerException, ex:
        print ex

