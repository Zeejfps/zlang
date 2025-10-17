using LLVMSharp.Interop;
using ParserModule.Nodes.Expressions;

namespace CodeGenModule;

public record FunctionSymbol(LLVMTypeRef TypeRef, LLVMValueRef ValueRef);